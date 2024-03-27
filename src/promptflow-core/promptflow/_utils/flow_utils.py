# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import hashlib
import json
import os
import re
from os import PathLike
from pathlib import Path
from typing import Optional, Tuple, Union

from promptflow._constants import CHAT_HISTORY, DEFAULT_ENCODING, DEFAULT_FLOW_YAML_FILE_NAME, PROMPT_FLOW_DIR_NAME
from promptflow._core._errors import MetaFileNotFound, MetaFileReadError
from promptflow._utils.logger_utils import LoggerFactory
from promptflow._utils.utils import strip_quotation
from promptflow._utils.yaml_utils import dump_yaml, load_yaml
from promptflow.contracts.flow import Flow as ExecutableFlow
from promptflow.exceptions import ErrorTarget, UserErrorException
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
    flow_path: Union[str, Path, PathLike], base_path: Union[str, Path, PathLike, None] = None, new: bool = False
) -> Tuple[Path, str]:
    """Resolve flow path and return the flow directory path and the file name of the target yaml.

    :param flow_path: The path of the flow directory or the flow yaml file. It can either point to a
      flow directory or a flow yaml file.
    :type flow_path: Union[str, Path, PathLike]
    :param base_path: The base path to resolve the flow path. If not specified, the flow path will be
      resolved based on the current working directory.
    :type base_path: Union[str, Path, PathLike]
    :param new: If True, the function will return the flow directory path and the file name of the
        target yaml that should be created. If False, the function will try to find the existing
        target yaml and raise FileNotFoundError if not found.
    :return: The flow directory path and the file name of the target yaml.
    :rtype: Tuple[Path, str]
    """
    if base_path:
        flow_path = Path(base_path) / flow_path
    else:
        flow_path = Path(flow_path)

    if new:
        if flow_path.is_dir():
            return flow_path, DEFAULT_FLOW_YAML_FILE_NAME
        return flow_path.parent, flow_path.name

    if flow_path.is_dir() and (flow_path / DEFAULT_FLOW_YAML_FILE_NAME).is_file():
        return flow_path, DEFAULT_FLOW_YAML_FILE_NAME
    elif flow_path.is_file():
        return flow_path.parent, flow_path.name

    raise FileNotFoundError(f"Can't find flow with path {flow_path.as_posix()}.")


def load_flow_dag(flow_path: Path):
    """Load flow dag from given flow path."""
    flow_dir, file_name = resolve_flow_path(flow_path)
    flow_path = flow_dir / file_name
    if not flow_path.exists():
        raise FileNotFoundError(f"Flow file {flow_path} not found")
    with open(flow_path, "r", encoding=DEFAULT_ENCODING) as f:
        flow_dag = load_yaml(f)
    return flow_path, flow_dag


def dump_flow_dag(flow_dag: dict, flow_path: Path):
    """Dump flow dag to given flow path."""
    flow_dir, flow_filename = resolve_flow_path(flow_path, new=True)
    flow_path = flow_dir / flow_filename
    with open(flow_path, "w", encoding=DEFAULT_ENCODING) as f:
        dump_yaml(flow_dag, f)
    return flow_path


def is_flex_flow(
    *, file_path: Union[str, Path, None] = None, yaml_dict: Optional[dict] = None, working_dir: Optional[Path] = None
):
    """Check if the flow is a flex flow."""
    if file_path is None and yaml_dict is None:
        raise UserErrorException("Either file_path or yaml_dict should be provided.")
    if file_path is not None and yaml_dict is not None:
        raise UserErrorException("Only one of file_path and yaml_dict should be provided.")
    if file_path is not None:
        file_path = Path(file_path)
        if working_dir is not None and not file_path.is_absolute():
            file_path = working_dir / file_path
        if file_path.suffix.lower() not in [".yaml", ".yml"]:
            return False
        yaml_dict = load_yaml(file_path)
    return isinstance(yaml_dict, dict) and "entry" in yaml_dict


def resolve_entry_file(entry: str, working_dir: Path) -> Optional[str]:
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
    elif len(chat_outputs) != 1:
        _is_chat_flow = False
        error_msg = "chat flow does not support multiple chat outputs"
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
