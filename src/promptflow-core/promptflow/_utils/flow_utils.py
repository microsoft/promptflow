# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import hashlib
import itertools
import json
import os
import re
from os import PathLike
from pathlib import Path
from typing import Optional, Tuple, Union

from promptflow._constants import (
    CHAT_HISTORY,
    DEFAULT_ENCODING,
    FLOW_DAG_YAML,
    FLOW_FILE_SUFFIX,
    FLOW_FLEX_YAML,
    PROMPT_FLOW_DIR_NAME,
    PROMPTY_EXTENSION,
    FlowType,
)
from promptflow._core._errors import MetaFileNotFound, MetaFileReadError
from promptflow._utils.logger_utils import LoggerFactory
from promptflow._utils.utils import convert_ordered_dict_to_dict, strip_quotation
from promptflow._utils.yaml_utils import dump_yaml, load_yaml
from promptflow.contracts.flow import Flow as ExecutableFlow
from promptflow.exceptions import ErrorTarget, UserErrorException, ValidationException
from promptflow.tracing._utils import serialize

logger = LoggerFactory.get_logger(name=__name__)


def get_flow_lineage_id(flow_dir: Union[str, PathLike]):
    """
    Get the lineage id for flow. The flow lineage id will be same for same flow in same GIT repo or device.
    If the flow locates in GIT repo:
        use Repo name + relative path to flow_dir as session id
    Otherwise:
        use device id + absolute path to flow_dir as session id
    :param flow_dir: flow directory
    """
    flow_dir = Path(flow_dir).resolve()
    if not flow_dir.is_dir():
        flow_dir = flow_dir.parent
    try:
        from git import Repo

        repo = Repo(flow_dir, search_parent_directories=True)
        lineage_id = f"{os.path.basename(repo.working_dir)}/{flow_dir.relative_to(repo.working_dir).as_posix()}"
        logger.debug("Got lineage id %s from git repo.", lineage_id)

    except Exception:
        # failed to get repo, use device id + absolute path to flow_dir as session id
        import uuid

        device_id = uuid.getnode()
        lineage_id = f"{device_id}/{flow_dir.absolute().as_posix()}"
        logger.debug("Got lineage id %s from local since failed to get git info.", lineage_id)

    # hash the value to avoid it gets too long, and it's not user visible.
    lineage_id = hashlib.sha256(lineage_id.encode()).hexdigest()
    return lineage_id


def resolve_flow_path(
    flow_path: Union[str, Path, PathLike],
    base_path: Union[str, Path, PathLike, None] = None,
    check_flow_exist: bool = True,
    default_flow_file: str = FLOW_DAG_YAML,
    allow_prompty_dir: bool = False,
) -> Tuple[Path, str]:
    """Resolve flow path and return the flow directory path and the file name of the target yaml.

    :param flow_path: The path of the flow directory or the flow yaml file. It can either point to a
      flow directory or a flow yaml file.
    :type flow_path: Union[str, Path, PathLike]
    :param base_path: The base path to resolve the flow path. If not specified, the flow path will be
      resolved based on the current working directory.
    :type base_path: Union[str, Path, PathLike]
    :param check_flow_exist: If True, the function will try to check the target yaml and
      raise FileNotFoundError if not found.
      If False, the function will return the flow directory path and the file name of the target yaml.
    :param default_flow_file: Default file name used when flow file is not found.
    :type default_flow_file: str
    :param allow_prompty_dir: If True along with check_flow_exist, the function will allow the flow path to be a
      directory with no yaml/yml but 1 and only 1 prompty in it.
    :return: The flow directory path and the file name of the target yaml.
    :rtype: Tuple[Path, str]
    """
    if base_path:
        flow_path = Path(base_path) / flow_path
    else:
        flow_path = Path(flow_path)

    prompty_count = -1
    if flow_path.is_dir():
        flow_folder = flow_path
        flow_file = default_flow_file
        flow_file_list = []
        for flow_name, suffix in itertools.product([FLOW_DAG_YAML, FLOW_FLEX_YAML], [".yaml", ".yml"]):
            flow_file_name = flow_name.replace(".yaml", suffix)
            if (flow_folder / flow_file_name).is_file():
                flow_file_list.append(flow_file_name)

        if len(flow_file_list) == 1:
            flow_file = flow_file_list[0]
        elif len(flow_file_list) > 1:
            raise ValidationException(
                f"Multiple files {', '.join(flow_file_list)} exist in {flow_path}. "
                f"Please specify a file or remove the extra YAML file.",
                privacy_info=[str(flow_path)],
            )
        elif allow_prompty_dir and check_flow_exist:
            candidates = list(flow_folder.glob(f"*{PROMPTY_EXTENSION}"))
            prompty_count = len(candidates)
            if len(candidates) == 1:
                flow_file = candidates[0].name
    elif flow_path.is_file() or flow_path.suffix.lower() in FLOW_FILE_SUFFIX:
        flow_folder = flow_path.parent
        flow_file = flow_path.name
    else:  # flow_path doesn't exist
        flow_folder = flow_path
        flow_file = default_flow_file

    file_path = flow_folder / flow_file
    if file_path.suffix.lower() not in FLOW_FILE_SUFFIX:
        raise UserErrorException(
            message_format="The flow file suffix must be yaml, yml or prompty; cannot be {suffix}",
            suffix=file_path.suffix,
        )

    if not check_flow_exist:
        return flow_folder.resolve().absolute(), flow_file

    if not flow_folder.exists():
        raise UserErrorException(
            f"Flow path {flow_path.absolute().as_posix()} does not exist.",
            privacy_info=[flow_path.absolute().as_posix()],
        )

    if not file_path.is_file() and flow_folder == flow_path:
        msg = f"Have found neither flow.dag.yaml nor flow.flex.yaml in {flow_path.absolute().as_posix()}"
        if prompty_count == 0 or not allow_prompty_dir:
            raise UserErrorException(
                msg,
                privacy_info=[flow_path.absolute().as_posix()],
            )
        else:
            raise UserErrorException(
                msg + " and there are more than 1 prompty file.",
                privacy_info=[flow_path.absolute().as_posix()],
            )
    if not file_path.is_file():
        raise UserErrorException(
            f"Flow file {file_path.absolute().as_posix()} does not exist.",
            privacy_info=[file_path.absolute().as_posix()],
        )

    return flow_folder.resolve().absolute(), flow_file


def load_flow_dag(flow_path: Path):
    """Load flow dag from given flow path."""
    flow_dir, file_name = resolve_flow_path(flow_path)
    flow_path = flow_dir / file_name
    if not flow_path.exists():
        raise FileNotFoundError(f"Flow file {flow_path} not found")
    with open(flow_path, "r", encoding=DEFAULT_ENCODING) as f:
        flow_dag = load_yaml(f)
    return flow_path, flow_dag


def dump_flow_yaml_to_existing_path(flow_dag: dict, flow_path: Path):
    """Dump flow dag to existing flow path (flow.dag.yaml or flow.flex.yaml). The YAML file is required to exist."""
    flow_dir, flow_filename = resolve_flow_path(flow_path, check_flow_exist=True)
    flow_path = flow_dir / flow_filename
    with open(flow_path, "w", encoding=DEFAULT_ENCODING) as f:
        # directly dumping ordered dict will bring !!omap tag in yaml
        dump_yaml(convert_ordered_dict_to_dict(flow_dag, remove_empty=False), f)
    return flow_path


def dump_flow_dag_according_to_content(flow_dag: dict, flow_path: Path):
    """Dump flow dag to YAML according to the content of flow_dag."""
    if is_flex_flow(yaml_dict=flow_dag):
        flow_filename = FLOW_FLEX_YAML
    else:
        flow_filename = FLOW_DAG_YAML
    flow_path = flow_path / flow_filename
    with open(flow_path, "w", encoding=DEFAULT_ENCODING) as f:
        # directly dumping ordered dict will bring !!omap tag in yaml
        dump_yaml(convert_ordered_dict_to_dict(flow_dag, remove_empty=False), f)
    return flow_path


def is_flex_flow(
    *,
    flow_path: Union[str, Path, PathLike, None] = None,
    yaml_dict: Optional[dict] = None,
    working_dir: Union[str, Path, PathLike, None] = None,
    check_flow_exist=True,
):
    """Check if the flow is a flex flow."""
    if flow_path is None and yaml_dict is None:
        raise UserErrorException("Either file_path or yaml_dict should be provided.")
    if flow_path is not None and yaml_dict is not None:
        raise UserErrorException("Only one of file_path and yaml_dict should be provided.")
    if flow_path is not None:
        flow_path, flow_file = resolve_flow_path(flow_path, base_path=working_dir, check_flow_exist=False)
        file_path = flow_path / flow_file
        if file_path.is_file() and file_path.suffix.lower() in (".yaml", ".yml"):
            yaml_dict = load_yaml(file_path)
        elif not check_flow_exist:
            return flow_file == FLOW_FLEX_YAML

    return isinstance(yaml_dict, dict) and "entry" in yaml_dict


def is_prompty_flow(file_path: Union[str, Path], raise_error: bool = False):
    """Check if the flow is a prompty flow by extension of the flow file is .prompty."""
    if not file_path or not Path(file_path).exists():
        if raise_error:
            raise UserErrorException(f"Cannot find the prompty file {file_path}.")
        else:
            return False
    return Path(file_path).suffix.lower() == PROMPTY_EXTENSION


def resolve_python_entry_file(entry: str, working_dir: Path) -> Optional[str]:
    """Resolve entry file from entry.
    If entry is a local file, e.g. my.local.file:entry_function, return the local file: my/local/file.py
        and executor will import it from local file.
    Else, assume the entry is from a package e.g. external.module:entry, return None
        and executor will try import it from package.
    """
    try:
        entry_file = f'{entry.split(":")[0].replace(".", "/")}.py'
    except Exception as e:
        raise UserErrorException(f"Entry function {entry} is not valid: {e}")
    entry_file = working_dir / entry_file
    if entry_file.exists():
        return entry_file.resolve().absolute().as_posix()
    # when entry file not found in working directory, return None since it can come from package
    return None


def read_json_content(file_path: Path, target: str) -> dict:
    if file_path.is_file():
        with open(file_path, mode="r", encoding=DEFAULT_ENCODING) as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                raise MetaFileReadError(
                    message_format="Failed to fetch {target_obj}: {file_path} is not a valid json file.",
                    file_path=file_path.absolute().as_posix(),
                    target_obj=target,
                )
    raise MetaFileNotFound(
        message_format=(
            "Failed to fetch meta of tools: cannot find {file_path}, "
            "please build the flow project with extension first."
        ),
        file_path=file_path.absolute().as_posix(),
    )


def dump_flow_result(flow_folder, prefix, flow_result=None, node_result=None, custom_path=None):
    """Dump flow result for extension.

    :param flow_folder: The flow folder.
    :param prefix: The file prefix.
    :param flow_result: The flow result returned by exec_line.
    :param node_result: The node result when test node returned by load_and_exec_node.
    :param custom_path: The custom path to dump flow result.
    """
    if flow_result:
        flow_serialize_result = {
            "flow_runs": [serialize(flow_result.run_info)],
            "node_runs": [serialize(run) for run in flow_result.node_run_infos.values()],
        }
    else:
        flow_serialize_result = {
            "flow_runs": [],
            "node_runs": [serialize(node_result)],
        }

    dump_folder = Path(flow_folder) / PROMPT_FLOW_DIR_NAME if custom_path is None else Path(custom_path)
    dump_folder.mkdir(parents=True, exist_ok=True)

    with open(dump_folder / f"{prefix}.detail.json", "w", encoding=DEFAULT_ENCODING) as f:
        json.dump(flow_serialize_result, f, indent=2, ensure_ascii=False)
    if node_result:
        metrics = flow_serialize_result["node_runs"][0]["metrics"]
        output = flow_serialize_result["node_runs"][0]["output"]
    else:
        metrics = flow_serialize_result["flow_runs"][0]["metrics"]
        output = flow_serialize_result["flow_runs"][0]["output"]
    if metrics:
        with open(dump_folder / f"{prefix}.metrics.json", "w", encoding=DEFAULT_ENCODING) as f:
            json.dump(metrics, f, indent=2, ensure_ascii=False)
    if output:
        with open(dump_folder / f"{prefix}.output.json", "w", encoding=DEFAULT_ENCODING) as f:
            json.dump(output, f, indent=2, ensure_ascii=False)


def is_executable_chat_flow(flow: ExecutableFlow):
    """
    Check if the flow is chat flow.
    Check if chat_history in the flow input and only one chat input and
    one chat output to determine if it is a chat flow.

    :param flow: The flow object.
    :type flow: promptflow.contracts.flow.Flow
    """
    chat_inputs = [item for item in flow.inputs.values() if item.is_chat_input]
    chat_outputs = [item for item in flow.outputs.values() if item.is_chat_output]
    chat_history_input_name = next(
        iter([input_name for input_name, value in flow.inputs.items() if value.is_chat_history]), None
    )
    if (
        not chat_history_input_name
        and CHAT_HISTORY in flow.inputs
        and flow.inputs[CHAT_HISTORY].is_chat_history is not False
    ):
        chat_history_input_name = CHAT_HISTORY
    _is_chat_flow, error_msg = True, ""
    if len(chat_inputs) != 1:
        _is_chat_flow = False
        error_msg = "chat flow does not support multiple chat inputs"
    elif len(chat_outputs) > 1:
        _is_chat_flow = False
        error_msg = "chat flow does not support multiple chat outputs"
    elif not chat_outputs and len(flow.outputs.values()) > 0:
        _is_chat_flow = False
        error_msg = "chat output is not configured"
    elif not chat_history_input_name:
        _is_chat_flow = False
        error_msg = "chat_history is required in the inputs of chat flow"
    return _is_chat_flow, chat_history_input_name, error_msg


def parse_variant(variant: str) -> Tuple[str, str]:
    variant_regex = r"\${([^.]+).([^}]+)}"
    match = re.match(variant_regex, strip_quotation(variant))
    if match:
        return match.group(1), match.group(2)
    else:
        error = ValueError(
            f"Invalid variant format: {variant}, variant should be in format of ${{TUNING_NODE.VARIANT}}"
        )
        raise UserErrorException(
            target=ErrorTarget.CONTROL_PLANE_SDK,
            message=str(error),
            error=error,
        )


def get_flow_type(flow_path: Union[str, Path, PathLike]) -> str:
    if not isinstance(flow_path, (str, Path, PathLike)):
        raise UserErrorException(f"flow_path type is {type(flow_path)}, but only support: str, Path, PathLike.")
    if is_prompty_flow(file_path=flow_path):
        return FlowType.PROMPTY
    if is_flex_flow(flow_path=flow_path):
        return FlowType.FLEX_FLOW
    return FlowType.DAG_FLOW
