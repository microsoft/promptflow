# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import collections
import datetime
import hashlib
import importlib
import inspect
import json
import os
import platform
import re
import shutil
import stat
import sys
import tempfile
import uuid
import zipfile
from contextlib import contextmanager
from enum import Enum
from functools import partial
from importlib.util import find_spec
from inspect import isfunction
from os import PathLike
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union, TypedDict
from urllib.parse import urlparse

import keyring
import pydash
from cryptography.fernet import Fernet
from filelock import FileLock
from keyring.errors import NoKeyringError
from marshmallow import ValidationError

from promptflow._constants import (
    ENABLE_MULTI_CONTAINER_KEY,
    EXTENSION_UA,
    FLOW_FLEX_YAML,
    LANGUAGE_KEY,
    PROMPTY_EXTENSION,
    FlowLanguage,
)
from promptflow._sdk._constants import (
    AZURE_WORKSPACE_REGEX_FORMAT,
    DEFAULT_ENCODING,
    FLOW_TOOLS_JSON,
    FLOW_TOOLS_JSON_GEN_TIMEOUT,
    HOME_PROMPT_FLOW_DIR,
    KEYRING_ENCRYPTION_KEY_NAME,
    KEYRING_ENCRYPTION_LOCK_PATH,
    KEYRING_SYSTEM,
    NODE,
    NODE_VARIANTS,
    NODES,
    PF_FLOW_ENTRY_IN_TMP,
    PROMPT_FLOW_DIR_NAME,
    REFRESH_CONNECTIONS_DIR_LOCK_PATH,
    REGISTRY_URI_PREFIX,
    REMOTE_URI_PREFIX,
    USE_VARIANTS,
    VARIANTS,
    AzureMLWorkspaceTriad,
    CommonYamlFields,
    RunInfoSources,
    RunMode,
)
from promptflow._sdk._errors import (
    DecryptConnectionError,
    GenerateFlowToolsJsonError,
    StoreConnectionEncryptionKeyError,
    UnsecureConnectionError,
)
from promptflow._sdk._vendor import IgnoreFile, get_ignore_file, get_upload_files_from_folder
from promptflow._utils.context_utils import inject_sys_path
from promptflow._utils.flow_utils import is_flex_flow, is_prompty_flow, resolve_flow_path
from promptflow._utils.logger_utils import get_cli_sdk_logger
from promptflow._utils.user_agent_utils import ClientUserAgentUtil
from promptflow._utils.yaml_utils import dump_yaml, load_yaml, load_yaml_string
from promptflow.contracts.tool import ToolType
from promptflow.core._utils import render_jinja_template_content
from promptflow.exceptions import ErrorTarget, UserErrorException, ValidationException

logger = get_cli_sdk_logger()


def find_type_in_override(params_override: Optional[list] = None) -> Optional[str]:
    params_override = params_override or []
    for override in params_override:
        if CommonYamlFields.TYPE in override:
            return override[CommonYamlFields.TYPE]
    return None


# region Encryption

CUSTOMIZED_ENCRYPTION_KEY_IN_KEY_RING = None
ENCRYPTION_KEY_IN_KEY_RING = None


@contextmanager
def use_customized_encryption_key(encryption_key: str):
    global CUSTOMIZED_ENCRYPTION_KEY_IN_KEY_RING

    CUSTOMIZED_ENCRYPTION_KEY_IN_KEY_RING = encryption_key
    yield
    CUSTOMIZED_ENCRYPTION_KEY_IN_KEY_RING = None


def set_encryption_key(encryption_key: Union[str, bytes]):
    if isinstance(encryption_key, bytes):
        encryption_key = encryption_key.decode("utf-8")
    keyring.set_password("promptflow", "encryption_key", encryption_key)


_encryption_key_lock = FileLock(KEYRING_ENCRYPTION_LOCK_PATH)


def get_encryption_key(generate_if_not_found: bool = False) -> str:
    global CUSTOMIZED_ENCRYPTION_KEY_IN_KEY_RING
    global ENCRYPTION_KEY_IN_KEY_RING
    if CUSTOMIZED_ENCRYPTION_KEY_IN_KEY_RING is not None:
        return CUSTOMIZED_ENCRYPTION_KEY_IN_KEY_RING
    if ENCRYPTION_KEY_IN_KEY_RING is not None:
        return ENCRYPTION_KEY_IN_KEY_RING

    def _get_from_keyring():
        try:
            # Cache encryption key as mac will pop window to ask for permission when calling get_password
            return keyring.get_password(KEYRING_SYSTEM, KEYRING_ENCRYPTION_KEY_NAME)
        except NoKeyringError as e:
            raise StoreConnectionEncryptionKeyError(
                "System keyring backend service not found in your operating system. "
                "See https://pypi.org/project/keyring/ to install requirement for different operating system, "
                "or 'pip install keyrings.alt' to use the third-party backend. Reach more detail about this error at "
                "https://microsoft.github.io/promptflow/how-to-guides/faq.html#connection-creation-failed-with-storeconnectionencryptionkeyerror"  # noqa: E501
            ) from e

    ENCRYPTION_KEY_IN_KEY_RING = _get_from_keyring()
    if ENCRYPTION_KEY_IN_KEY_RING is not None or not generate_if_not_found:
        return ENCRYPTION_KEY_IN_KEY_RING
    _encryption_key_lock.acquire()
    # Note: we access the keyring twice, as global var can't share across processes.
    ENCRYPTION_KEY_IN_KEY_RING = _get_from_keyring()
    if ENCRYPTION_KEY_IN_KEY_RING is not None:
        return ENCRYPTION_KEY_IN_KEY_RING
    try:
        ENCRYPTION_KEY_IN_KEY_RING = Fernet.generate_key().decode("utf-8")
        keyring.set_password(KEYRING_SYSTEM, KEYRING_ENCRYPTION_KEY_NAME, ENCRYPTION_KEY_IN_KEY_RING)
    finally:
        _encryption_key_lock.release()
    return ENCRYPTION_KEY_IN_KEY_RING


def encrypt_secret_value(secret_value):
    encryption_key = get_encryption_key(generate_if_not_found=True)
    fernet_client = Fernet(encryption_key)
    token = fernet_client.encrypt(secret_value.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_secret_value(connection_name, encrypted_secret_value):
    encryption_key = get_encryption_key()
    if encryption_key is None:
        raise Exception("Encryption key not found in keyring.")
    fernet_client = Fernet(encryption_key)
    try:
        return fernet_client.decrypt(encrypted_secret_value.encode("utf-8")).decode("utf-8")
    except Exception as e:
        if len(encrypted_secret_value) < 57:
            # This is to workaround old custom secrets that are not encrypted with Fernet.
            # Fernet token: https://github.com/fernet/spec/blob/master/Spec.md
            # Format: Version ‖ Timestamp ‖ IV ‖ Ciphertext ‖ HMAC
            # Version: 8 bits, Timestamp: 64 bits, IV: 128 bits, HMAC: 256 bits,
            # Ciphertext variable length, multiple of 128 bits
            # So the minimum length of a Fernet token is 57 bytes
            raise UnsecureConnectionError(
                f"Please delete and re-create connection {connection_name} "
                f"due to a security issue in the old sdk version."
            )
        raise DecryptConnectionError(
            f"Decrypt connection {connection_name} secret failed: {str(e)}. "
            f"If you have ever changed your encryption key manually, "
            f"please revert it back to the original one, or delete all connections and re-create them."
        )


# endregion


def decorate_validation_error(schema: Any, pretty_error: str, additional_message: str = "") -> str:
    return f"Validation for {schema.__name__} failed:\n\n {pretty_error} \n\n {additional_message}"


def load_from_dict(schema: Any, data: Dict, context: Dict, additional_message: str = "", **kwargs):
    try:
        return schema(context=context).load(data, **kwargs)
    except ValidationError as e:
        pretty_error = json.dumps(e.normalized_messages(), indent=2)
        raise ValidationException(decorate_validation_error(schema, pretty_error, additional_message))


def render_jinja_template(template_path, *, trim_blocks=True, keep_trailing_newline=True, **kwargs):
    with open(template_path, "r", encoding=DEFAULT_ENCODING) as f:
        return render_jinja_template_content(
            f.read(), trim_blocks=trim_blocks, keep_trailing_newline=keep_trailing_newline, **kwargs
        )


def print_yellow_warning(message):
    from colorama import Fore, init

    init(autoreset=True)
    print(Fore.YELLOW + message)


def print_red_error(message):
    from colorama import Fore, init

    init(autoreset=True)
    print(Fore.RED + message)


def safe_parse_object_list(obj_list, parser, message_generator):
    results = []
    for obj in obj_list:
        try:
            results.append(parser(obj))
        except Exception as e:
            extended_message = f"{message_generator(obj)} Error: {type(e).__name__}, {str(e)}"
            print_yellow_warning(extended_message)
    return results


def _sanitize_python_variable_name(name: str):
    from promptflow._utils.utils import _sanitize_python_variable_name

    return _sanitize_python_variable_name(name)


def _get_additional_includes(yaml_path):
    if not is_prompty_flow(yaml_path):
        flow_dag = load_yaml(yaml_path)
        return flow_dag.get("additional_includes", [])
    return []


def _is_folder_to_compress(path: Path) -> bool:
    """Check if the additional include needs to compress corresponding folder as a zip.

    For example, given additional include /mnt/c/hello.zip
      1) if a file named /mnt/c/hello.zip already exists, return False (simply copy)
      2) if a folder named /mnt/c/hello exists, return True (compress as a zip and copy)

    :param path: Given path in additional include.
    :type path: Path
    :return: If the path need to be compressed as a zip file.
    :rtype: bool
    """
    if path.suffix != ".zip":
        return False
    # if zip file exists, simply copy as other additional includes
    if path.exists():
        return False
    # remove .zip suffix and check whether the folder exists
    stem_path = path.parent / path.stem
    return stem_path.is_dir()


def _resolve_folder_to_compress(base_path: Path, include: str, dst_path: Path) -> None:
    """resolve the zip additional include, need to compress corresponding folder."""
    zip_additional_include = (base_path / include).resolve()
    folder_to_zip = zip_additional_include.parent / zip_additional_include.stem
    zip_file = dst_path / zip_additional_include.name
    with zipfile.ZipFile(zip_file, "w") as zf:
        zf.write(folder_to_zip, os.path.relpath(folder_to_zip, folder_to_zip.parent))  # write root in zip
        for root, _, files in os.walk(folder_to_zip, followlinks=True):
            for file in files:
                file_path = os.path.join(folder_to_zip, file)
                zf.write(file_path, os.path.relpath(file_path, folder_to_zip.parent))


@contextmanager
def _merge_local_code_and_additional_includes(code_path: Path):
    # TODO: unify variable names: flow_dir_path, flow_file_path, flow_path

    def additional_includes_copy(src, relative_path, target_dir):
        if src.is_file():
            dst = Path(target_dir) / relative_path
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                logger.warning(
                    "Found duplicate file in additional includes, "
                    f"additional include file {src} will overwrite {relative_path}"
                )
            shutil.copy2(src, dst)
        else:
            for name in src.glob("*"):
                additional_includes_copy(name, Path(relative_path) / name.name, target_dir)

    code_path, yaml_file = resolve_flow_path(code_path, check_flow_exist=False)
    yaml_path = code_path / yaml_file

    with tempfile.TemporaryDirectory() as temp_dir:
        shutil.copytree(code_path.resolve().as_posix(), temp_dir, dirs_exist_ok=True)
        for item in _get_additional_includes(yaml_path):
            src_path = Path(str(item))
            if not src_path.is_absolute():
                src_path = (code_path / item).resolve()

            if _is_folder_to_compress(src_path):
                _resolve_folder_to_compress(code_path, item, Path(temp_dir))
                # early continue as the folder is compressed as a zip file
                continue

            if not src_path.exists():
                error = ValueError(f"Unable to find additional include {item}")
                raise UserErrorException(
                    target=ErrorTarget.CONTROL_PLANE_SDK, message=str(error), error=error, privacy_info=[item]
                )

            additional_includes_copy(src_path, relative_path=src_path.name, target_dir=temp_dir)
        yield temp_dir


def incremental_print(log: str, printed: int, fileout) -> int:
    count = 0
    for line in log.splitlines():
        if count >= printed:
            fileout.write(line + "\n")
            printed += 1
        count += 1
    return printed


def get_promptflow_sdk_version() -> str:
    try:
        import promptflow

        return promptflow.__version__
    except (ImportError, AttributeError):
        # if promptflow is not installed from root, it does not have __version__ attribute
        return None


def get_promptflow_tracing_version() -> Union[str, None]:
    try:
        from promptflow.tracing._version import __version__

        return __version__
    except ImportError:
        return None


def get_promptflow_core_version() -> Union[str, None]:
    try:
        from promptflow.core._version import __version__

        return __version__
    except ImportError:
        return None


def get_promptflow_devkit_version() -> Union[str, None]:
    try:
        from promptflow._sdk._version import __version__

        return __version__
    except ImportError:
        return None


def get_promptflow_azure_version() -> Union[str, None]:
    try:
        from promptflow.azure._version import __version__

        return __version__
    except ImportError:
        return None


def get_promptflow_evals_version() -> Union[str, None]:
    try:
        from promptflow.evals._version import __version__

        return __version__
    except ImportError:
        return None


def print_promptflow_version_dict_string(with_azure: bool = False, ignore_none: bool = False):
    version_dict = {"promptflow": get_promptflow_sdk_version()}
    # check tracing version
    version_tracing = get_promptflow_tracing_version()
    if version_tracing:
        version_dict["promptflow-tracing"] = version_tracing
    # check core version
    version_core = get_promptflow_core_version()
    if version_core:
        version_dict["promptflow-core"] = version_core
    # check devkit version
    version_devkit = get_promptflow_devkit_version()
    if version_devkit:
        version_dict["promptflow-devkit"] = version_devkit

    if with_azure:
        # check azure version
        version_azure = get_promptflow_azure_version()
        if version_azure:
            version_dict["promptflow-azure"] = version_azure

    # check evals version
    version_evals = get_promptflow_evals_version()
    if version_evals:
        version_dict["promptflow-evals"] = version_evals

    if ignore_none:
        version_dict = {k: v for k, v in version_dict.items() if v is not None}
    version_dict_string = (
        json.dumps(version_dict, ensure_ascii=False, indent=2, sort_keys=True, separators=(",", ": ")) + "\n"
    )
    print(version_dict_string)


def print_pf_version(with_azure: bool = False, ignore_none: bool = False):
    print_promptflow_version_dict_string(with_azure, ignore_none)
    print("Executable '{}'".format(os.path.abspath(sys.executable)))
    print("Python ({}) {}".format(platform.system(), sys.version))


class PromptflowIgnoreFile(IgnoreFile):
    # TODO add more files to this list.
    IGNORE_FILE = [".git", ".runs", "__pycache__"]

    def __init__(self, prompt_flow_path: Union[Path, str]):
        super(PromptflowIgnoreFile, self).__init__(prompt_flow_path)
        self._path = Path(prompt_flow_path)
        self._ignore_tools_json = False

    @property
    def base_path(self) -> Path:
        return self._path

    def _get_ignore_list(self):
        """Get ignore list from ignore file contents."""
        if not self.exists():
            return []

        base_ignore = get_ignore_file(self.base_path)
        result = self.IGNORE_FILE + base_ignore._get_ignore_list()
        if self._ignore_tools_json:
            result.append(f"{PROMPT_FLOW_DIR_NAME}/{FLOW_TOOLS_JSON}")
        return result


def _construct_tool_dict(tools: List[Tuple[str, str]]) -> Dict[str, Dict[str, str]]:
    """Construct tool dict from tool list.

    :param tools: tool list, like [('test.py', 'python'), ('test.jinja2', 'llm')]
    :return: tool dict, like
    {
        'test.py': {
            'tool_type': 'python'
        },
        'test.jinja2': {
            'tool_type': 'llm'
        }
    }
    """
    return {source: {"tool_type": tool_type} for source, tool_type in tools}


def _generate_tool_meta(
    flow_directory: Path,
    tools: List[Tuple[str, str]],
    raise_error: bool,
    timeout: int,
    *,
    include_errors_in_output: bool = False,
    load_in_subprocess: bool = True,
) -> Dict[str, dict]:
    """Generate tool meta from files.

    :param flow_directory: flow directory
    :param tools: tool list
    :param raise_error: whether raise error when generate meta failed
    :param timeout: timeout for generate meta
    :param include_errors_in_output: whether include errors in output
    :param load_in_subprocess: whether load tool meta with subprocess to prevent system path disturb. Default is True.
        If set to False, will load tool meta in sync mode and timeout need to be handled outside current process.
    :return: tool meta dict
    """
    from promptflow._core.tool_meta_generator import generate_tool_meta, generate_tool_meta_in_subprocess

    tools = _construct_tool_dict(tools)
    if load_in_subprocess:
        # use multiprocess generate to avoid system path disturb
        tool_dict, exception_dict = generate_tool_meta_in_subprocess(flow_directory, tools, logger, timeout=timeout)
    else:
        #  There is no built-in method to forcefully stop a running thread/coroutine in Python
        #  because abruptly stopping a thread can cause issues like resource leaks,
        #  deadlocks, or inconsistent states.
        #  Caller needs to handle the timeout outside current process.
        logger.warning(
            "Generate meta in current process and timeout won't take effect. "
            "Please handle timeout manually outside current process."
        )
        tool_dict, exception_dict = generate_tool_meta(flow_directory, tools)
    res = {source: tool for source, tool in tool_dict.items()}

    for source in res:
        # remove name in tool meta
        res[source].pop("name")
        # convert string Enum to string
        if isinstance(res[source]["type"], Enum):
            res[source]["type"] = res[source]["type"].value
        # not all tools have inputs, so check first
        if "inputs" in res[source]:
            for tool_input in res[source]["inputs"]:
                tool_input_type = res[source]["inputs"][tool_input]["type"]
                for i in range(len(tool_input_type)):
                    if isinstance(tool_input_type[i], Enum):
                        tool_input_type[i] = tool_input_type[i].value

    # collect errors and print warnings, exception_dict is a dict of source and error dict
    errors = {source: error_dict.get("message", "unknown exception") for source, error_dict in exception_dict.items()}
    for source in errors:
        if include_errors_in_output:
            res[source] = errors[source]
        else:
            logger.warning(f"Generate meta for source {source!r} failed: {errors[source]}.")
    if raise_error and len(errors) > 0:
        error_message = "Generate meta failed, detail error(s):\n" + json.dumps(errors, indent=4)
        raise GenerateFlowToolsJsonError(error_message)
    return res


FunctionConfig = TypedDict("FunctionConfig", {
    "func_path": str,
    "func_kwargs": Dict,
    "azureml_workspace": Optional[AzureMLWorkspaceTriad],
}, total=False)


def _retrieve_tool_func_result(func_call_scenario: str, function_config: FunctionConfig):
    """Retrieve tool func result according to func_call_scenario.

    :param func_call_scenario: function call scenario
    :param function_config: function config in tool meta. Should contain 'func_path' and 'func_kwargs'.
    :return: func call result according to func_call_scenario.
    """
    from promptflow._core.tools_manager import retrieve_tool_func_result

    func_path = function_config.get("func_path", "")
    func_kwargs = function_config.get("func_kwargs", {})
    # May call azure control plane api in the custom function to list Azure resources.
    # which may need Azure workspace triple.
    # TODO: move this method to a common place.
    from promptflow._cli._utils import get_workspace_triad_from_local

    azureml_workspace = function_config.get("azureml_workspace", None)
    workspace_triad = AzureMLWorkspaceTriad(
        subscription_id=azureml_workspace["subscription_id"],
        resource_group_name=azureml_workspace["resource_group_name"],
        workspace_name=azureml_workspace["workspace_name"]
    ) if azureml_workspace is not None else get_workspace_triad_from_local()

    if workspace_triad.subscription_id and workspace_triad.resource_group_name and workspace_triad.workspace_name:
        result = retrieve_tool_func_result(func_call_scenario, func_path, func_kwargs, workspace_triad._asdict())
    # if no workspace triple available, just skip.
    else:
        result = retrieve_tool_func_result(func_call_scenario, func_path, func_kwargs)

    result_with_log = {"result": result, "logs": {}}
    return result_with_log


def _generate_package_tools(keys: Optional[List[str]] = None) -> dict:
    from promptflow._core.tools_manager import collect_package_tools

    return collect_package_tools(keys=keys)


def _update_involved_tools_and_packages(
    _node,
    _node_path,
    *,
    tools: List,
    used_packages: Set,
    source_path_mapping: Dict[str, List[str]],
):
    source, tool_type = pydash.get(_node, "source.path", None), _node.get("type", None)

    used_packages.add(pydash.get(_node, "source.tool", None))

    if source is None or tool_type is None:
        return

    # for custom LLM tool, its source points to the used prompt template so handle it as prompt tool
    if tool_type == ToolType.CUSTOM_LLM:
        tool_type = ToolType.PROMPT

    if pydash.get(_node, "source.type") not in ["code", "package_with_prompt"]:
        return
    pair = (source, tool_type.lower())
    if pair not in tools:
        tools.append(pair)

    source_path_mapping[source].append(f"{_node_path}.source.path")


def _get_involved_code_and_package(
    data: dict,
) -> Tuple[List[Tuple[str, str]], Set[str], Dict[str, List[str]]]:
    tools = []  # List[Tuple[source_file, tool_type]]
    used_packages = set()
    source_path_mapping = collections.defaultdict(list)

    for node_i, node in enumerate(data[NODES]):
        _update_involved_tools_and_packages(
            node,
            f"{NODES}.{node_i}",
            tools=tools,
            used_packages=used_packages,
            source_path_mapping=source_path_mapping,
        )

        # understand DAG to parse variants
        # TODO: should we allow source to appear both in node and node variants?
        if node.get(USE_VARIANTS) is True:
            node_variants = data[NODE_VARIANTS][node["name"]]
            for variant_id in node_variants[VARIANTS]:
                node_with_variant = node_variants[VARIANTS][variant_id][NODE]
                _update_involved_tools_and_packages(
                    node_with_variant,
                    f"{NODE_VARIANTS}.{node['name']}.{VARIANTS}.{variant_id}.{NODE}",
                    tools=tools,
                    used_packages=used_packages,
                    source_path_mapping=source_path_mapping,
                )
    if None in used_packages:
        used_packages.remove(None)
    return tools, used_packages, source_path_mapping


def generate_flow_tools_json(
    flow_directory: Union[str, Path],
    dump: bool = True,
    raise_error: bool = True,
    timeout: int = FLOW_TOOLS_JSON_GEN_TIMEOUT,
    *,
    include_errors_in_output: bool = False,
    target_source: str = None,
    used_packages_only: bool = False,
    source_path_mapping: Dict[str, List[str]] = None,
) -> dict:
    """Generate flow.tools.json for a flow directory.

    :param flow_directory: path to flow directory.
    :param dump: whether to dump to .promptflow/flow.tools.json, default value is True.
    :param raise_error: whether to raise the error, default value is True.
    :param timeout: timeout for generation, default value is 60 seconds.
    :param include_errors_in_output: whether to include error messages in output, default value is False.
    :param target_source: the source name to filter result, default value is None. Note that we will update system path
        in coroutine if target_source is provided given it's expected to be from a specific cli call.
    :param used_packages_only: whether to only include used packages, default value is False.
    :param source_path_mapping: if specified, record yaml paths for each source.
    """
    flow_directory, flow_file = resolve_flow_path(flow_directory, check_flow_exist=False)
    # parse flow DAG
    data = load_yaml(flow_directory / flow_file)

    tools, used_packages, _source_path_mapping = _get_involved_code_and_package(data)

    # update passed in source_path_mapping if specified
    if source_path_mapping is not None:
        source_path_mapping.update(_source_path_mapping)

    # filter tools by target_source if specified
    if target_source is not None:
        tools = list(filter(lambda x: x[0] == target_source, tools))

    # generate content
    # TODO: remove type in tools (input) and code (output)
    flow_tools = {
        "code": _generate_tool_meta(
            flow_directory,
            tools,
            raise_error=raise_error,
            timeout=timeout,
            include_errors_in_output=include_errors_in_output,
            # we don't need to protect system path according to the target usage when target_source is specified
            load_in_subprocess=target_source is None,
        ),
        # specified source may only appear in code tools
        "package": {}
        if target_source is not None
        else _generate_package_tools(keys=list(used_packages) if used_packages_only else None),
    }

    if dump:
        # dump as flow.tools.json
        promptflow_folder = flow_directory / PROMPT_FLOW_DIR_NAME
        promptflow_folder.mkdir(exist_ok=True)
        with open(promptflow_folder / FLOW_TOOLS_JSON, mode="w", encoding=DEFAULT_ENCODING) as f:
            json.dump(flow_tools, f, indent=4)

    return flow_tools


def call_from_extension() -> bool:
    """Return true if current request is from extension."""
    ClientUserAgentUtil.update_user_agent_from_env_var()
    user_agent = ClientUserAgentUtil.get_user_agent()
    return EXTENSION_UA in user_agent


def generate_random_string(length: int = 6) -> str:
    import random
    import string

    return "".join(random.choice(string.ascii_lowercase) for _ in range(length))


def copy_tree_respect_template_and_ignore_file(source: Path, target: Path, render_context: dict = None):
    def is_template(path: str):
        return path.endswith(".jinja2")

    for source_path, target_path in get_upload_files_from_folder(
        path=source,
        ignore_file=PromptflowIgnoreFile(prompt_flow_path=source),
    ):
        (target / target_path).parent.mkdir(parents=True, exist_ok=True)
        if render_context is None or not is_template(source_path):
            shutil.copy(source_path, target / target_path)
        else:
            (target / target_path[: -len(".jinja2")]).write_bytes(
                # always use unix line ending
                render_jinja_template(source_path, **render_context)
                .encode("utf-8")
                .replace(b"\r\n", b"\n"),
            )


def _generate_connections_dir():
    # Get Python executable path
    python_path = sys.executable

    # Hash the Python executable path
    hash_object = hashlib.sha1(python_path.encode())
    hex_dig = hash_object.hexdigest()

    # Generate the connections system path using the hash
    connections_dir = (HOME_PROMPT_FLOW_DIR / "envs" / hex_dig / "connections").resolve()
    return connections_dir


_refresh_connection_dir_lock = FileLock(REFRESH_CONNECTIONS_DIR_LOCK_PATH)


# This function is used by extension to generate the connection files every time collect tools.
def refresh_connections_dir(connection_spec_files, connection_template_yamls):
    connections_dir = _generate_connections_dir()

    # Use lock to prevent concurrent access
    with _refresh_connection_dir_lock:
        if os.path.isdir(connections_dir):
            shutil.rmtree(connections_dir)
        os.makedirs(connections_dir)

        if connection_spec_files and connection_template_yamls:
            for connection_name, content in connection_spec_files.items():
                file_name = connection_name + ".spec.json"
                with open(connections_dir / file_name, "w", encoding=DEFAULT_ENCODING) as f:
                    json.dump(content, f, indent=2)

            # use YAML to dump template file in order to keep the comments
            for connection_name, content in connection_template_yamls.items():
                yaml_data = load_yaml_string(content)
                file_name = connection_name + ".template.yaml"
                with open(connections_dir / file_name, "w", encoding=DEFAULT_ENCODING) as f:
                    dump_yaml(yaml_data, f)


def read_write_by_user():
    return stat.S_IRUSR | stat.S_IWUSR


def remove_empty_element_from_dict(obj: dict) -> dict:
    """Remove empty element from dict, e.g. {"a": 1, "b": {}} -> {"a": 1}"""
    new_dict = {}
    for key, value in obj.items():
        if isinstance(value, dict):
            value = remove_empty_element_from_dict(value)
        if value is not None:
            new_dict[key] = value
    return new_dict


def is_multi_container_enabled():
    if ENABLE_MULTI_CONTAINER_KEY in os.environ:
        return os.environ[ENABLE_MULTI_CONTAINER_KEY].lower() == "true"
    return None


def is_url(value: Union[PathLike, str]) -> bool:
    try:
        result = urlparse(str(value))
        return all([result.scheme, result.netloc])
    except ValueError:
        return False


def is_remote_uri(obj) -> bool:
    # return True if it's supported remote uri
    if isinstance(obj, str):
        if obj.startswith(REMOTE_URI_PREFIX):
            # azureml: started, azureml:name:version, azureml://xxx
            return True
        elif is_url(obj):
            return True
    return False


def parse_remote_flow_pattern(flow: object) -> str:
    # Check if the input matches the correct pattern
    flow_name = None
    error_message = (
        f"Invalid remote flow pattern, got {flow!r} while expecting "
        f"a remote workspace flow like '{REMOTE_URI_PREFIX}<flow-name>', or a remote registry flow like "
        f"'{REMOTE_URI_PREFIX}//registries/<registry-name>/models/<flow-name>/versions/<version>'"
    )
    if not isinstance(flow, str) or not flow.startswith(REMOTE_URI_PREFIX):
        raise UserErrorException(error_message)

    # check for registry flow pattern
    if flow.startswith(REGISTRY_URI_PREFIX):
        pattern = r"azureml://registries/.*?/models/(?P<name>.*?)/versions/(?P<version>.*?)$"
        match = re.match(pattern, flow)
        if not match or len(match.groups()) != 2:
            raise UserErrorException(error_message)
        flow_name, _ = match.groups()
    # check for workspace flow pattern
    elif flow.startswith(REMOTE_URI_PREFIX):
        pattern = r"azureml:(?P<name>.*?)$"
        match = re.match(pattern, flow)
        if not match or len(match.groups()) != 1:
            raise UserErrorException(error_message)
        flow_name = match.groups()[0]
    return flow_name


# extract open read/write as partial to centralize the encoding
read_open = partial(open, mode="r", encoding=DEFAULT_ENCODING)
write_open = partial(open, mode="w", encoding=DEFAULT_ENCODING)
# nan, inf and -inf are not JSON serializable according to https://docs.python.org/3/library/json.html#json.loads
# `parse_constant` will be called to handle these values
# similar idea for below `json_load` and its parameter `parse_const_as_str`
json_loads_parse_const_as_str = partial(json.loads, parse_constant=lambda x: str(x))


# extract some file operations inside this file
def json_load(file, parse_const_as_str: bool = False) -> str:
    with read_open(file) as f:
        if parse_const_as_str is True:
            return json.load(f, parse_constant=lambda x: str(x))
        else:
            return json.load(f)


def json_dump(obj, file) -> None:
    with write_open(file) as f:
        json.dump(obj, f, ensure_ascii=False)


def pd_read_json(file) -> "DataFrame":
    import pandas as pd

    with read_open(file) as f:
        return pd.read_json(f, orient="records", lines=True)


def get_mac_address() -> str:
    """Obtain all MAC addresses, then sort and concatenate them."""
    try:
        import psutil

        mac_address = []
        net_addresses = psutil.net_if_addrs()
        # Obtain all MAC addresses, then sort and concatenate them
        net_address_list = sorted(net_addresses.items())  # sort by name
        for name, net_address in net_address_list:
            for net_interface in net_address:
                if net_interface.family == psutil.AF_LINK and net_interface.address != "00-00-00-00-00-00":
                    mac_address.append(net_interface.address)

        return ":".join(mac_address)
    except Exception as e:
        logger.debug(f"get mac id error: {str(e)}")
        return ""


def get_system_info() -> Tuple[str, str, str]:
    """Get the host name, system, and machine."""
    try:
        import platform

        return platform.node(), platform.system(), platform.machine()
    except Exception as e:
        logger.debug(f"get host name error: {str(e)}")
        return "", "", ""


def gen_uuid_by_compute_info() -> Union[str, None]:
    mac_address = get_mac_address()
    host_name, system, machine = get_system_info()
    if mac_address:
        # Use sha256 convert host_name+system+machine to a fixed length string
        # and concatenate it after the mac address to ensure that the concatenated string is unique.
        system_info_hash = hashlib.sha256((host_name + system + machine).encode()).hexdigest()
        compute_info_hash = hashlib.sha256((mac_address + system_info_hash).encode()).hexdigest()
        return str(uuid.uuid5(uuid.NAMESPACE_OID, compute_info_hash))
    return str(uuid.uuid4())


def convert_time_unix_nano_to_timestamp(time_unix_nano: str) -> datetime.datetime:
    nanoseconds = int(time_unix_nano)
    seconds = nanoseconds / 1_000_000_000
    return datetime.datetime.utcfromtimestamp(seconds)


def extract_workspace_triad_from_trace_provider(trace_provider: str) -> AzureMLWorkspaceTriad:
    match = re.match(AZURE_WORKSPACE_REGEX_FORMAT, trace_provider)
    if not match or len(match.groups()) != 5:
        raise ValueError(
            "Malformed trace provider string, expected azureml://subscriptions/<subscription_id>/"
            "resourceGroups/<resource_group>/providers/Microsoft.MachineLearningServices/"
            f"workspaces/<workspace_name>, got {trace_provider}"
        )
    subscription_id = match.group(1)
    resource_group_name = match.group(3)
    workspace_name = match.group(5)
    return AzureMLWorkspaceTriad(subscription_id, resource_group_name, workspace_name)


def overwrite_null_std_logger():
    # For the process started in detach mode, stdout/stderr will be none.
    # To avoid exception to stdout/stderr calls in the dependency package, point stdout/stderr to devnull.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = sys.stdout


def generate_yaml_entry_without_delete(entry: Union[str, PathLike, Callable], code: Path = None):
    """Generate a flex flow yaml in temp folder and won't delete it."""
    from promptflow._proxy import ProxyFactory

    executor_proxy = ProxyFactory().get_executor_proxy_cls(FlowLanguage.Python)
    if callable(entry) or executor_proxy.is_flex_flow_entry(entry=entry):
        temp_dir = tempfile.mkdtemp()
        flow_yaml_path = create_flex_flow_yaml_in_target(entry, temp_dir, code)
        return flow_yaml_path
    else:
        if code:
            logger.warning(f"Specify code {code} is only supported for Python flex flow entry, ignoring it.")
        return entry


@contextmanager
def generate_yaml_entry(entry: Union[str, PathLike, Callable], code: Path = None):
    """Generate yaml entry to run."""
    from promptflow._proxy import ProxyFactory
    from promptflow._sdk.entities._flows.base import FlowBase

    executor_proxy = ProxyFactory().get_executor_proxy_cls(FlowLanguage.Python)
    if not isinstance(entry, FlowBase) and (callable(entry) or executor_proxy.is_flex_flow_entry(entry=entry)):
        with create_temp_flex_flow_yaml(entry, code) as flow_yaml_path:
            yield flow_yaml_path
    else:
        if code:
            logger.warning(f"Specify code {code} is only supported for Python flex flow entry, ignoring it.")
        yield entry


def resolve_entry_and_code(entry: Union[str, PathLike, Callable], code: Path = None):
    if callable(entry):
        entry = callable_to_entry_string(entry)
    if not code:
        code = Path.cwd()
    else:
        code = Path(code)
        if not code.exists():
            raise UserErrorException(f"Code path {code.as_posix()} does not exist.")
    return entry, code


def create_flex_flow_yaml_in_target(entry: Union[str, PathLike, Callable], target_dir: str, code: Path = None) -> Path:
    """
    Generate a flex flow yaml in target folder. The code field in the yaml points to the original flex yaml flow folder.
    """
    from promptflow._utils.flow_utils import dump_flow_dag_according_to_content

    logger.info("Create temporary entry for flex flow.")
    entry, code = resolve_entry_and_code(entry, code)
    flow_dag = {"entry": entry}
    code = "." if Path(target_dir).resolve().as_posix() == code.resolve().as_posix() else str(code.resolve())
    flow_dag.update({"code": code})
    flow_yaml_path = dump_flow_dag_according_to_content(flow_dag=flow_dag, flow_path=Path(target_dir))
    return flow_yaml_path


def create_temp_flex_flow_yaml_core(entry: Union[str, PathLike, Callable], code: Path = None):
    logger.info("Create temporary entry for flex flow.")
    entry, code = resolve_entry_and_code(entry, code)
    flow_yaml_path = code / FLOW_FLEX_YAML
    existing_content = None

    if flow_yaml_path.exists():
        logger.warning(f"Found existing {flow_yaml_path.as_posix()}, will not respect it in runtime.")
        with open(flow_yaml_path, "r", encoding=DEFAULT_ENCODING) as f:
            existing_content = f.read()

    create_yaml_in_tmp = False
    if os.environ.get(PF_FLOW_ENTRY_IN_TMP, "False").lower() == "true":
        logger.debug("PF_FLOW_ENTRY_IN_TMP is set to true, its snapshot will be empty.")
        create_yaml_in_tmp = True
    elif not is_local_module(entry_string=entry, code=code):
        logger.debug(f"Entry {entry} is not found in local, its snapshot will be empty.")
        create_yaml_in_tmp = True

    if create_yaml_in_tmp:
        # make sure run name is from entry instead of random folder name
        temp_dir = tempfile.mkdtemp(prefix=_sanitize_python_variable_name(entry) + "_")
        flow_yaml_path = Path(temp_dir) / FLOW_FLEX_YAML
    with open(flow_yaml_path, "w", encoding=DEFAULT_ENCODING) as f:
        dump_yaml({"entry": entry}, f)
    return flow_yaml_path, existing_content


@contextmanager
def create_temp_flex_flow_yaml(entry: Union[str, PathLike, Callable], code: Path = None):
    """Create a temporary flow.dag.yaml in code folder"""
    flow_yaml_path, existing_content = create_temp_flex_flow_yaml_core(entry, code)
    try:
        yield flow_yaml_path
    finally:
        # delete the file or recover the content
        if flow_yaml_path.exists():
            if existing_content:
                with open(flow_yaml_path, "w", encoding=DEFAULT_ENCODING) as f:
                    f.write(existing_content)
            else:
                try:
                    flow_yaml_path.unlink()
                except Exception as e:
                    logger.warning(f"Failed to delete generated: {flow_yaml_path.as_posix()}, error: {e}")


def can_accept_kwargs(func):
    sig = inspect.signature(func)
    params = sig.parameters.values()
    return any(param.kind == param.VAR_KEYWORD for param in params)


def callable_to_entry_string(callable_obj: Callable) -> str:
    """Convert callable object to entry string."""
    if not isfunction(callable_obj) and not hasattr(callable_obj, "__call__"):
        raise UserErrorException(
            f"{callable_obj} is not function or callable object, only function or callable object are supported."
        )

    try:
        module_str = callable_obj.__module__
        func_str = callable_obj.__name__
    except AttributeError as e:
        raise UserErrorException(
            f"Failed to convert {callable_obj} to entry, please make sure it has __module__ and __name__"
        ) from e

    # check if callable can be imported from module
    module = importlib.import_module(module_str)
    func = getattr(module, func_str, None)
    if not func:
        raise UserErrorException(
            f"Failed to import {callable_obj} from module {module}, please make sure it's a global function."
        )

    return f"{module_str}:{func_str}"


def is_local_module(entry_string: str, code: Path) -> bool:
    """Return True if the module is from local file."""
    try:
        with inject_sys_path(code):
            module, _ = entry_string.split(":")
            spec = find_spec(module)
            origin = spec.origin
            module_path = module.replace(".", "/") + ".py"
            module_path = code / module_path
            if Path(origin) == module_path:
                return True
    except Exception as e:
        logger.debug(f"Failed to check is local module from {entry_string} due to {e}.")
        return False


def is_flex_run(run: "Run") -> bool:
    if run._run_source == RunInfoSources.LOCAL:
        try:
            # The flow yaml may have been temporarily generated and deleted after creating a run.
            # So check_flow_exist=False.
            return is_flex_flow(flow_path=run.flow, check_flow_exist=False)
        except Exception as e:
            # For run with incomplete flow snapshot, ignore load flow error to make sure it can still show.
            logger.debug(f"Failed to check is flex flow from {run.flow} due to {e}.")
            return False
    elif run._run_source in [RunInfoSources.INDEX_SERVICE, RunInfoSources.RUN_HISTORY]:
        return run._properties.get("azureml.promptflow.run_mode") == RunMode.EAGER
    # TODO(2901279): support eager mode for run created from run folder
    return False


def get_flow_name(flow) -> str:
    if isinstance(flow, Path):
        return flow.resolve().name

    from promptflow._sdk.entities._flows.dag import Flow as DAGFlow

    if isinstance(flow, DAGFlow):
        return flow.name
    # should be promptflow._sdk.entities._flows.base.FlowBase: flex flow, prompty, etc.
    return flow.code.name


def add_executable_script_to_env_path():
    # Add executable script dir to PATH to make sure the subprocess can find the executable, especially in notebook
    # environment which won't add it to system path automatically.
    python_dir = os.path.dirname(sys.executable)
    executable_dir = os.path.join(python_dir, "Scripts") if platform.system() == "Windows" else python_dir
    if executable_dir not in os.environ["PATH"].split(os.pathsep):
        os.environ["PATH"] = executable_dir + os.pathsep + os.environ["PATH"]


def get_flow_path(flow) -> Path:
    # use public API to get flow path for DAG/flex flow or prompty
    from promptflow._sdk.entities._flows.dag import Flow as DAGFlow
    from promptflow._sdk.entities._flows.flex import FlexFlow
    from promptflow._sdk.entities._flows.prompty import Prompty

    if isinstance(flow, DAGFlow):
        return flow._flow_file_path.parent.resolve()
    if isinstance(flow, (FlexFlow, Prompty)):
        # Use code path to return as flow path, since code path is the same as flow directory for yaml case and code
        # path points to original code path in non-yaml case
        return flow.code.resolve()
    raise ValueError(f"Unsupported flow type {type(flow)!r}")


def load_input_data(data_path):
    from promptflow._utils.load_data import load_data

    if not Path(data_path).exists():
        raise ValueError(f"Cannot find inputs file {data_path}")
    if data_path.endswith(".jsonl"):
        return load_data(local_path=data_path)[0]
    elif data_path.endswith(".json"):
        with open(data_path, "r") as f:
            return json.load(f)
    else:
        raise ValueError("Only support jsonl or json file as input.")


def resolve_flow_language(
    *,
    flow_path: Union[str, Path, PathLike, None] = None,
    yaml_dict: Optional[dict] = None,
    working_dir: Union[str, Path, PathLike, None] = None,
    # add kwargs given this function will be used in runtime and may have more parameters in the future
    **kwargs,
) -> str:
    """Get language of a flow. Will return 'python' for Prompty."""
    if flow_path is None and yaml_dict is None:
        raise UserErrorException("Either flow_path or yaml_dict should be provided.")
    if flow_path is not None and yaml_dict is not None:
        raise UserErrorException("Only one of flow_path and yaml_dict should be provided.")
    if flow_path is not None:
        # flow path must exist
        flow_path, flow_file = resolve_flow_path(flow_path, base_path=working_dir, check_flow_exist=True)
        file_path = flow_path / flow_file
        if file_path.suffix.lower() in (".yaml", ".yml"):
            yaml_dict = load_yaml(file_path)
        elif file_path.suffix.lower() == PROMPTY_EXTENSION:
            return FlowLanguage.Python
        else:
            # actually suffix is already checked in resolve_flow_path
            raise UserErrorException(f"Invalid flow path {file_path.as_posix()}, must of suffix yaml, yml or prompty.")
    return yaml_dict.get(LANGUAGE_KEY, FlowLanguage.Python)


def get_trace_destination(pf_client=None):
    """get trace.destination

    :param pf_client: pf_client object
    :type pf_client: promptflow._sdk._pf_client.PFClient
    :return:
    """
    from promptflow._sdk._configuration import Configuration

    config = pf_client._config if pf_client else Configuration.get_instance()
    trace_destination = config.get_trace_destination()

    return trace_destination
