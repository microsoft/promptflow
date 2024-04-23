# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import hashlib
import inspect
import itertools
import json
import os
import re
from os import PathLike
from pathlib import Path
from typing import Callable, List, Optional, Tuple, Union

from promptflow._constants import (
    CHAT_HISTORY,
    DEFAULT_ENCODING,
    FLOW_DAG_YAML,
    FLOW_FILE_SUFFIX,
    FLOW_FLEX_YAML,
    LANGUAGE_KEY,
    PROMPT_FLOW_DIR_NAME,
    PROMPTY_EXTENSION,
)
from promptflow._core._errors import MetaFileNotFound, MetaFileReadError
from promptflow._utils.logger_utils import LoggerFactory
from promptflow._utils.utils import strip_quotation
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
    :return: The flow directory path and the file name of the target yaml.
    :rtype: Tuple[Path, str]
    """
    if base_path:
        flow_path = Path(base_path) / flow_path
    else:
        flow_path = Path(flow_path)

    if flow_path.is_dir():
        flow_folder = flow_path
        flow_file = FLOW_DAG_YAML
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
    elif flow_path.is_file() or flow_path.suffix.lower() in FLOW_FILE_SUFFIX:
        flow_folder = flow_path.parent
        flow_file = flow_path.name
    else:  # flow_path doesn't exist
        flow_folder = flow_path
        flow_file = FLOW_DAG_YAML

    file_path = flow_folder / flow_file
    if file_path.suffix.lower() not in FLOW_FILE_SUFFIX:
        raise UserErrorException(
            error_format=f"The flow file suffix must be yaml or yml, and cannot be {file_path.suffix}"
        )

    if not check_flow_exist:
        return flow_folder.resolve().absolute(), flow_file

    if not flow_folder.exists():
        raise UserErrorException(
            f"Flow path {flow_path.absolute().as_posix()} does not exist.",
            privacy_info=[flow_path.absolute().as_posix()],
        )

    if not file_path.is_file():
        if flow_folder == flow_path:
            raise UserErrorException(
                f"Flow path {flow_path.absolute().as_posix()} "
                f"must have postfix either {FLOW_DAG_YAML} or {FLOW_FLEX_YAML}",
                privacy_info=[flow_path.absolute().as_posix()],
            )
        else:
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


def dump_flow_dag(flow_dag: dict, flow_path: Path):
    """Dump flow dag to given flow path."""
    flow_dir, flow_filename = resolve_flow_path(flow_path, check_flow_exist=False)
    flow_path = flow_dir / flow_filename
    with open(flow_path, "w", encoding=DEFAULT_ENCODING) as f:
        dump_yaml(flow_dag, f)
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


def format_signature_type(flow_meta):
    # signature is language irrelevant, so we apply json type system
    # TODO: enable this mapping after service supports more types
    value_type_map = {
        # ValueType.INT.value: SignatureValueType.INT.value,
        # ValueType.DOUBLE.value: SignatureValueType.NUMBER.value,
        # ValueType.LIST.value: SignatureValueType.ARRAY.value,
        # ValueType.BOOL.value: SignatureValueType.BOOL.value,
    }
    for port_type in ["inputs", "outputs", "init"]:
        if port_type not in flow_meta:
            continue
        for port_name, port in flow_meta[port_type].items():
            if port["type"] in value_type_map:
                port["type"] = value_type_map[port["type"]]


def _validate_flow_meta(flow_meta: dict, language: str, code: Path):
    flow_meta["language"] = language
    # TODO: change this implementation to avoid using FlexFlow?
    # this path is actually not used
    from promptflow._sdk.entities._flows import FlexFlow

    flow = FlexFlow(path=code / FLOW_FLEX_YAML, code=code, data=flow_meta, entry=flow_meta["entry"])
    flow._validate(raise_error=True)


def infer_signature_for_flex_flow(
    entry: Union[Callable, str],
    *,
    language: str,
    code: str = None,
    keep_entry: bool = False,
    validate: bool = True,
    include_primitive_output: bool = False,
) -> Tuple[dict, Path, List[str]]:
    """Infer signature of a flow entry."""
    snapshot_list = None
    # resolve entry and code
    if isinstance(entry, str):
        if not code:
            raise UserErrorException("Code path is required when entry is a string.")
        code = Path(code)
        if not code.exists():
            raise UserErrorException(f"Specified code {code} does not exist.")
        if code.is_file():
            snapshot_list = [code.name]
            entry = f"{code.stem}:{entry}"
            code = code.parent

        # import this locally to avoid circular import
        from promptflow._proxy import ProxyFactory

        inspector_proxy = ProxyFactory().create_inspector_proxy(language=language)

        if not inspector_proxy.is_flex_flow_entry(entry):
            raise UserErrorException(f"Entry {entry} is not a valid entry for flow.")

        # TODO: extract description?
        flow_meta = inspector_proxy.get_entry_meta(entry=entry, working_dir=code)
    elif code is not None:
        # TODO: support specifying code when inferring signature?
        raise UserErrorException(
            "Code path will be the parent of entry source " "and can't be customized when entry is a callable."
        )
    elif inspect.isclass(entry) or inspect.isfunction(entry):
        if inspect.isclass(entry):
            if not hasattr(entry, "__call__"):
                raise UserErrorException("Class entry must have a __call__ method.")
            f, cls = entry.__call__, entry
        else:
            f, cls = entry, None

        # callable entry must be of python, so we directly import from promptflow._core locally here
        from promptflow._core.tool_meta_generator import generate_flow_meta_dict_by_object

        flow_meta = generate_flow_meta_dict_by_object(f, cls)
        source_path = Path(inspect.getfile(entry))
        code = source_path.parent
        # TODO: should we handle the case that entry is not defined in root level of the source?
        flow_meta["entry"] = f"{source_path.stem}:{entry.__name__}"
    else:
        raise UserErrorException("Entry must be a function or a class.")

    format_signature_type(flow_meta)

    if validate:
        _validate_flow_meta(flow_meta, language, code)

    if include_primitive_output and "outputs" not in flow_meta:
        flow_meta["outputs"] = {
            "output": {
                "type": "string",
            }
        }

    keys_to_keep = ["inputs", "outputs", "init"]
    if keep_entry:
        keys_to_keep.append("entry")
    filtered_meta = {k: flow_meta[k] for k in keys_to_keep if k in flow_meta}
    return filtered_meta, code, snapshot_list


def merge_flow_signature(extracted, signature_overrides):
    if not signature_overrides:
        signature_overrides = {}

    signature = {}
    for key in ["inputs", "outputs", "init"]:
        if key in extracted:
            signature[key] = extracted[key]
        elif key in signature_overrides:
            raise UserErrorException(f"Provided signature for {key}, which can't be overridden according to the entry.")

        if key not in signature_overrides:
            continue

        if set(extracted[key].keys()) != set(signature_overrides[key].keys()):
            raise UserErrorException(
                f"Provided signature of {key} does not match the entry.\n"
                f"Ports from signature: {', '.join(signature_overrides[key].keys())}\n"
                f"Ports from entry: {', '.join(signature[key].keys())}\n"
            )

        # TODO: merge the signature
        signature[key] = signature_overrides[key]

    return signature


def update_signatures(code: Path, data: dict) -> bool:
    """Update signatures for flex flow. Raise validation error if signature is not valid."""
    if not is_flex_flow(yaml_dict=data):
        return False
    entry = data.get("entry")
    signatures, _, _ = infer_signature_for_flex_flow(
        entry=entry,
        code=code.as_posix(),
        language=data.get(LANGUAGE_KEY, "python"),
        validate=False,
        include_primitive_output=True,
    )
    merged_signatures = merge_flow_signature(extracted=signatures, signature_overrides=data)
    updated = False
    for field in ["inputs", "outputs", "init"]:
        if merged_signatures.get(field) != data.get(field):
            updated = True
    data.update(merged_signatures)
    from promptflow._sdk.entities._flows import FlexFlow

    FlexFlow(path=code / FLOW_FLEX_YAML, code=code, data=data, entry=entry)._validate(raise_error=True)
    return updated
