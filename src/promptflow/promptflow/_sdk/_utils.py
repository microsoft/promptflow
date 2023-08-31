# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import collections
import json
import logging
import multiprocessing
import os
import re
import shutil
import tempfile
from contextlib import contextmanager
from enum import Enum
from os import PathLike
from pathlib import Path
from typing import IO, Any, AnyStr, Dict, List, Optional, Tuple, Union
import zipfile

import keyring
import yaml
from cryptography.fernet import Fernet
from filelock import FileLock
from jinja2 import Template
from keyring.errors import NoKeyringError
from marshmallow import ValidationError

import promptflow
from promptflow._core.tool_meta_generator import generate_tool_meta_dict_by_file
from promptflow._sdk._constants import (
    DAG_FILE_NAME,
    DEFAULT_ENCODING,
    FLOW_TOOLS_JSON,
    FLOW_TOOLS_JSON_GEN_TIMEOUT,
    KEYRING_ENCRYPTION_KEY_NAME,
    KEYRING_ENCRYPTION_LOCK_PATH,
    KEYRING_SYSTEM,
    LOGGER_NAME,
    NODE,
    NODE_VARIANTS,
    NODES,
    PROMPT_FLOW_DIR_NAME,
    USE_VARIANTS,
    VARIANTS,
    CommonYamlFields,
)
from promptflow._sdk._errors import (
    DecryptConnectionError,
    GenerateFlowToolsJsonError,
    StoreConnectionEncryptionKeyError,
    UnsecureConnectionError,
)
from promptflow._sdk._vendor import IgnoreFile, get_ignore_file, get_upload_files_from_folder
from promptflow._utils.context_utils import _change_working_dir, inject_sys_path
from promptflow.contracts.tool import ToolType


def snake_to_camel(name):
    return re.sub(r"(?:^|_)([a-z])", lambda x: x.group(1).upper(), name)


def find_type_in_override(params_override: Optional[list] = None) -> Optional[str]:
    params_override = params_override or []
    for override in params_override:
        if CommonYamlFields.TYPE in override:
            return override[CommonYamlFields.TYPE]
    return None


def load_yaml(source: Optional[Union[AnyStr, PathLike, IO]]) -> Dict:
    # null check - just return an empty dict.
    # Certain CLI commands rely on this behavior to produce a resource
    # via CLI, which is then populated through CLArgs.
    """Load a local YAML file.

    :param source: The relative or absolute path to the local file.
    :type source: str
    :return: A dictionary representation of the local file's contents.
    :rtype: Dict
    """
    # These imports can't be placed in at top file level because it will cause a circular import in
    # exceptions.py via _get_mfe_url_override

    if source is None:
        return {}

    # pylint: disable=redefined-builtin
    input = None
    must_open_file = False
    try:  # check source type by duck-typing it as an IOBase
        readable = source.readable()
        if not readable:  # source is misformatted stream or file
            msg = "File Permissions Error: The already-open \n\n inputted file is not readable."
            raise Exception(msg)
        # source is an already-open stream or file, we can read() from it directly.
        input = source
    except AttributeError:
        # source has no writable() function, assume it's a string or file path.
        must_open_file = True

    if must_open_file:  # If supplied a file path, open it.
        try:
            input = open(source, "r")
        except OSError:  # FileNotFoundError introduced in Python 3
            msg = "No such file or directory: {}"
            raise Exception(msg.format(source))
    # input should now be an readable file or stream. Parse it.
    cfg = {}
    try:
        cfg = yaml.safe_load(input)
    except yaml.YAMLError as e:
        msg = f"Error while parsing yaml file: {source} \n\n {str(e)}"
        raise Exception(msg)
    finally:
        if must_open_file:
            input.close()
    return cfg


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
                "or 'pip install keyrings.alt' to use the third-party backend. Reach more detail about this error at"
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


def dump_yaml(*args, **kwargs):
    """A thin wrapper over yaml.dump which forces `OrderedDict`s to be serialized as mappings.

    Other behaviors identically to yaml.dump
    """

    class OrderedDumper(yaml.Dumper):
        """A modified yaml serializer that forces pyyaml to represent an OrderedDict as a mapping instead of a
        sequence."""

    OrderedDumper.add_representer(collections.OrderedDict, yaml.representer.SafeRepresenter.represent_dict)
    return yaml.dump(*args, Dumper=OrderedDumper, **kwargs)


def decorate_validation_error(schema: Any, pretty_error: str, additional_message: str = "") -> str:
    return f"Validation for {schema.__name__} failed:\n\n {pretty_error} \n\n {additional_message}"


def load_from_dict(schema: Any, data: Dict, context: Dict, additional_message: str = "", **kwargs):
    try:
        return schema(context=context).load(data, **kwargs)
    except ValidationError as e:
        pretty_error = json.dumps(e.normalized_messages(), indent=2)
        raise ValidationError(decorate_validation_error(schema, pretty_error, additional_message))


def parse_variant(variant: str) -> Tuple[str, str]:
    variant_regex = r"\${([^.]+).([^}]+)}"
    match = re.match(variant_regex, variant)
    if match:
        return match.group(1), match.group(2)
    else:
        raise ValueError(f"Invalid variant format: {variant}, variant should be in format of ${{TUNING_NODE.VARIANT}}")


def _match_reference(env_val: str):
    env_val = env_val.strip()
    m = re.match(r"^\$\{([^.]+)\.([^.]+)}$", env_val)
    if not m:
        return None, None
    name, key = m.groups()
    return name, key


# !!! Attention!!!: Please make sure you have contact with PRS team before changing the interface.
def get_used_connection_names_from_environment_variables():
    """The function will get all potential related connection names from current environment variables.
    for example, if part of env var is
    {
      "ENV_VAR_1": "${my_connection.key}",
      "ENV_VAR_2": "${my_connection.key2}",
      "ENV_VAR_3": "${my_connection2.key}",
    }
    The function will return {"my_connection", "my_connection2"}.
    """
    return get_used_connection_names_from_dict(os.environ)


def get_used_connection_names_from_dict(connection_dict: dict):
    connection_names = set()
    for key, val in connection_dict.items():
        connection_name, _ = _match_reference(val)
        if connection_name:
            connection_names.add(connection_name)

    return connection_names


# !!! Attention!!!: Please make sure you have contact with PRS team before changing the interface.
def update_environment_variables_with_connections(built_connections):
    """The function will result env var value ${my_connection.key} to the real connection keys."""
    return update_dict_value_with_connections(built_connections, os.environ)


def _match_env_reference(val: str):
    val = val.strip()
    m = re.match(r"^\$\{env:(.+)}$", val)
    if not m:
        return None
    name = m.groups()[0]
    return name


def resolve_connections_environment_variable_reference(connections: Dict[str, dict]):
    """The function will resolve connection secrets env var reference like api_key: ${env:KEY}"""
    for connection in connections.values():
        values = connection.get("value", {})
        for key, val in values.items():
            if not _match_env_reference(val):
                continue
            env_name = _match_env_reference(val)
            if env_name not in os.environ:
                raise Exception(f"Environment variable {env_name} is not found.")
            values[key] = os.environ[env_name]
    return connections


def update_dict_value_with_connections(built_connections, connection_dict: dict):
    for key, val in connection_dict.items():
        connection_name, connection_key = _match_reference(val)
        if connection_name is None:
            continue
        if connection_name not in built_connections:
            continue
        if connection_key not in built_connections[connection_name]["value"]:
            continue
        connection_dict[key] = built_connections[connection_name]["value"][connection_key]


def in_jupyter_notebook() -> bool:
    """
    Checks if user is using a Jupyter Notebook. This is necessary because logging is not allowed in
    non-Jupyter contexts.

    Adapted from https://stackoverflow.com/a/22424821
    """
    try:  # cspell:ignore ipython
        from IPython import get_ipython

        if "IPKernelApp" not in get_ipython().config:
            return False
    except ImportError:
        return False
    except AttributeError:
        return False
    return True


def render_jinja_template(template_path, *, trim_blocks=True, keep_trailing_newline=True, **kwargs):
    with open(template_path, "r") as f:
        template = Template(f.read(), trim_blocks=trim_blocks, keep_trailing_newline=keep_trailing_newline)
    return template.render(**kwargs)


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


def _normalize_identifier_name(name):
    normalized_name = name.lower()
    normalized_name = re.sub(r"[\W_]", " ", normalized_name)  # No non-word characters
    normalized_name = re.sub(" +", " ", normalized_name).strip()  # No double spaces, leading or trailing spaces
    if re.match(r"\d", normalized_name):
        normalized_name = "n" + normalized_name  # No leading digits
    return normalized_name


def _sanitize_python_variable_name(name: str):
    return _normalize_identifier_name(name).replace(" ", "_")


def _get_additional_includes(yaml_path):
    with open(yaml_path, "r") as f:
        flow_dag = yaml.safe_load(f)
    return flow_dag.get("additional_includes", [])


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
    # TODO: unify variable names: flow_dir_path, flow_dag_path, flow_path
    logger = logging.getLogger(LOGGER_NAME)

    def additional_includes_copy(src, dst, base_path):
        if src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                try:
                    relative_path = dst.relative_to(Path(temp_dir).resolve())
                except Exception:
                    relative_path = dst
                logger.warning("Found duplicate file in additional includes, "
                               f"additional include file {src} will overwrite {relative_path}")
            shutil.copy2(src, dst)
        else:
            for name in src.glob("*"):
                additional_includes_copy(name, dst / name.name, base_path)

    if code_path.is_dir():
        yaml_path = (Path(code_path) / DAG_FILE_NAME).resolve()
        code_path = code_path.resolve()
    else:
        yaml_path = code_path.resolve()
        code_path = code_path.parent.resolve()

    with tempfile.TemporaryDirectory() as temp_dir:
        shutil.copytree(code_path.resolve().as_posix(), temp_dir, dirs_exist_ok=True)
        for item in _get_additional_includes(yaml_path):
            src_path = Path(item)
            if not src_path.is_absolute():
                src_path = (code_path / item).resolve()
            dst_path = (Path(temp_dir) / src_path.name).resolve()

            if _is_folder_to_compress(src_path):
                _resolve_folder_to_compress(code_path, item, Path(temp_dir))
                # early continue as the folder is compressed as a zip file
                continue

            if not src_path.exists():
                raise ValueError(f"Unable to find additional include {item}")

            additional_includes_copy(src_path, dst_path, temp_dir)
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
        return promptflow.__version__
    except AttributeError:
        # if promptflow is installed from source, it does not have __version__ attribute
        return "0.0.1"


class PromptflowIgnoreFile(IgnoreFile):

    # TODO add more files to this list.
    IGNORE_FILE = [".runs", "__pycache__"]

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


def _generate_metas_from_files(
    tools: List[Tuple[str, str]], flow_directory: Path, tools_dict: dict, exception_dict: dict
) -> None:
    with _change_working_dir(flow_directory), inject_sys_path(flow_directory):
        for source, tool_type in tools:
            try:
                tools_dict[source] = generate_tool_meta_dict_by_file(source, ToolType(tool_type))
            except Exception as e:
                exception_dict[source] = str(e)


def _generate_tool_meta(
    flow_directory: Path,
    tools: List[Tuple[str, str]],
    raise_error: bool,
    timeout: int,
) -> Dict[str, dict]:
    logger = logging.getLogger(LOGGER_NAME)
    # use multi process generate to avoid system path disturb
    manager = multiprocessing.Manager()
    tools_dict = manager.dict()
    exception_dict = manager.dict()
    p = multiprocessing.Process(
        target=_generate_metas_from_files, args=(tools, flow_directory, tools_dict, exception_dict)
    )
    p.start()
    p.join(timeout=timeout)
    if p.is_alive():
        p.terminate()
        p.join()
    res = {source: tool for source, tool in tools_dict.items()}

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

    # collect errors and print warnings
    errors = {
        source: exception for source, exception in exception_dict.items()
    }  # for not processed tools, regard as timeout error
    for source, _ in tools:
        if source not in res and source not in errors:
            errors[source] = f"Generate meta timeout for source {source!r}."
    for source in errors:
        logger.warning(f"Generate meta for source {source!r} failed: {errors[source]}.")
    if raise_error and len(errors) > 0:
        error_message = "Generate meta failed, detail error(s):\n" + json.dumps(errors, indent=4)
        raise GenerateFlowToolsJsonError(error_message)
    return res


def _generate_package_tools() -> dict:
    import imp

    import pkg_resources

    imp.reload(pkg_resources)

    from promptflow._core.tools_manager import collect_package_tools

    return collect_package_tools()


def generate_flow_tools_json(
    flow_directory: Union[str, Path],
    dump: bool = True,
    raise_error: bool = True,
    timeout: int = FLOW_TOOLS_JSON_GEN_TIMEOUT,
) -> dict:
    """Generate flow.tools.json for a flow directory.

    :param flow_directory: path to flow directory.
    :param dump: whether to dump to .promptflow/flow.tools.json, default value is True.
    :param raise_error: whether to raise the error, default value is True.
    :param timeout: timeout for generation, default value is 60 seconds.
    """
    flow_directory = Path(flow_directory).resolve()
    # parse flow DAG
    with open(flow_directory / DAG_FILE_NAME, "r") as f:
        data = yaml.safe_load(f)
    tools = []  # List[Tuple[source_file, tool_type]]
    for node in data[NODES]:
        if "source" in node:
            if node["source"]["type"] != "code":
                continue
            if not (flow_directory / node["source"]["path"]).exists():
                continue
            tools.append((node["source"]["path"], node["type"].lower()))
        # understand DAG to parse variants
        elif node.get(USE_VARIANTS) is True:
            node_variants = data[NODE_VARIANTS][node["name"]]
            for variant_id in node_variants[VARIANTS]:
                current_node = node_variants[VARIANTS][variant_id][NODE]
                if current_node["source"]["type"] != "code":
                    continue
                if not (flow_directory / current_node["source"]["path"]).exists():
                    continue
                tools.append((current_node["source"]["path"], current_node["type"].lower()))

    # generate content
    flow_tools = {
        "package": _generate_package_tools(),
        "code": _generate_tool_meta(flow_directory, tools, raise_error=raise_error, timeout=timeout),
    }

    if dump:
        # dump as flow.tools.json
        promptflow_folder = flow_directory / PROMPT_FLOW_DIR_NAME
        promptflow_folder.mkdir(exist_ok=True)
        with open(promptflow_folder / FLOW_TOOLS_JSON, mode="w", encoding=DEFAULT_ENCODING) as f:
            json.dump(flow_tools, f, indent=4)

    return flow_tools


def setup_user_agent_to_operation_context(user_agent):
    from promptflow._core.operation_context import OperationContext

    if "USER_AGENT" in os.environ:
        # Append vscode or other user agent from env
        OperationContext.get_instance().append_user_agent(os.environ["USER_AGENT"])
    # Append user agent
    OperationContext.get_instance().append_user_agent(user_agent)


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
