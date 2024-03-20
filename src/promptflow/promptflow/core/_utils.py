# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import json
import multiprocessing
import re
from pathlib import Path
from typing import Dict, List, Mapping, Union

from jinja2 import Template

from promptflow._constants import DEFAULT_ENCODING, FLOW_META_JSON, FLOW_META_JSON_GEN_TIMEOUT, PROMPT_FLOW_DIR_NAME
from promptflow._utils.context_utils import _change_working_dir, inject_sys_path
from promptflow._utils.flow_utils import is_flex_flow, resolve_entry_file, resolve_flow_path
from promptflow._utils.logger_utils import LoggerFactory
from promptflow._utils.yaml_utils import load_yaml
from promptflow.core._connection import AzureOpenAIConnection, OpenAIConnection
from promptflow.core._errors import (
    ChatAPIFunctionRoleInvalidFormatError,
    ChatAPIInvalidRoleError,
    CoreError,
    GenerateFlowMetaJsonError,
    InvalidConnectionError,
    InvalidConnectionTypeError,
)

logger = LoggerFactory.get_logger(name=__name__)


def _generate_meta_from_file(working_dir, source_path, entry, meta_dict, exception_list):
    from promptflow._core.tool_meta_generator import generate_flow_meta_dict_by_file

    with _change_working_dir(working_dir), inject_sys_path(working_dir):
        try:
            result = generate_flow_meta_dict_by_file(
                path=source_path,
                entry=entry,
            )
            meta_dict.update(result)
        except Exception as e:
            exception_list.append(str(e))


def _generate_flow_meta(
    flow_directory: Path,
    source_path: str,
    entry: str,
    timeout: int,
    *,
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
    if load_in_subprocess:
        # use multiprocess generate to avoid system path disturb
        manager = multiprocessing.Manager()
        meta_dict = manager.dict()
        exception_list = manager.list()
        p = multiprocessing.Process(
            target=_generate_meta_from_file, args=(flow_directory, source_path, entry, meta_dict, exception_list)
        )
        p.start()
        p.join(timeout=timeout)
        if p.is_alive():
            logger.warning(f"Generate meta timeout after {timeout} seconds, terminate the process.")
            p.terminate()
            p.join()
    else:
        meta_dict, exception_list = {}, []

        #  There is no built-in method to forcefully stop a running thread/coroutine in Python
        #  because abruptly stopping a thread can cause issues like resource leaks,
        #  deadlocks, or inconsistent states.
        #  Caller needs to handle the timeout outside current process.
        logger.warning(
            "Generate meta in current process and timeout won't take effect. "
            "Please handle timeout manually outside current process."
        )
        _generate_meta_from_file(flow_directory, source_path, entry, meta_dict, exception_list)
    # directly raise error if failed to generate meta
    if len(exception_list) > 0:
        error_message = "Generate meta failed, detail error:\n" + str(exception_list)
        raise GenerateFlowMetaJsonError(error_message)
    return dict(meta_dict)


def generate_flow_meta(
    flow_directory: Union[str, Path],
    source_path: str,
    entry: str,
    dump: bool = True,
    timeout: int = FLOW_META_JSON_GEN_TIMEOUT,
    load_in_subprocess: bool = True,
) -> dict:
    """Generate flow.json for a flow directory."""

    flow_meta = _generate_flow_meta(
        flow_directory=flow_directory,
        source_path=source_path,
        entry=entry,
        timeout=timeout,
        load_in_subprocess=load_in_subprocess,
    )

    if dump:
        # dump as flow.tools.json
        promptflow_folder = flow_directory / PROMPT_FLOW_DIR_NAME
        promptflow_folder.mkdir(exist_ok=True)
        with open(promptflow_folder / FLOW_META_JSON, mode="w", encoding=DEFAULT_ENCODING) as f:
            json.dump(flow_meta, f, indent=4)

    return flow_meta


def render_jinja_template_content(template_content, *, trim_blocks=True, keep_trailing_newline=True, **kwargs):
    template = Template(template_content, trim_blocks=trim_blocks, keep_trailing_newline=keep_trailing_newline)
    return template.render(**kwargs)


def get_connection(connection):
    if not isinstance(connection, (str, dict)):
        error_message = """
        Illegal definition of connection. Need to provide connection name or connection info like below:
        connection:
            type: <connection_type>
            api_key: <api_key>
            api_base: <api_base>
            ...
        """
        raise InvalidConnectionError(message=error_message)
    if isinstance(connection, str):
        # Get connection by name
        try:
            from promptflow._sdk._pf_client import PFClient
        except ImportError as ex:
            raise CoreError(f"Please try 'pip install promptflow-devkit' to install dependency, {ex.msg}")
        client = PFClient()
        connection_obj = client.connections.get(connection, with_secrets=True)
        connection = connection_obj._to_execution_connection_dict()["value"]
        connection_type = connection_obj.TYPE
    else:
        connection_type = connection.pop("type", None)
    if connection_type == AzureOpenAIConnection.TYPE:
        return AzureOpenAIConnection(**connection)
    elif connection_type == OpenAIConnection.TYPE:
        return OpenAIConnection(**connection)
    error_message = (
        f"Not Support connection type {connection_type} for embedding api. "
        f"Connection type should be in [{AzureOpenAIConnection.TYPE}, {OpenAIConnection.TYPE}]."
    )
    raise InvalidConnectionTypeError(message=error_message)


# region: Copied from promptflow-tools


def normalize_connection_config(connection):
    """
    Normalizes the configuration of a given connection object for compatibility.

    This function takes a connection object and normalizes its configuration,
    ensuring it is compatible and standardized for use.
    """
    if isinstance(connection, AzureOpenAIConnection):
        if connection.api_key:
            return {
                # disable OpenAI's built-in retry mechanism by using our own retry
                # for better debuggability and real-time status updates.
                "max_retries": 0,
                "api_key": connection.api_key,
                "api_version": connection.api_version,
                "azure_endpoint": connection.api_base,
            }
        else:
            return {
                "max_retries": 0,
                "api_version": connection.api_version,
                "azure_endpoint": connection.api_base,
                "azure_ad_token_provider": connection.get_token,
            }
    elif isinstance(connection, OpenAIConnection):
        return {
            "max_retries": 0,
            "api_key": connection.api_key,
            "organization": connection.organization,
            "base_url": connection.base_url,
        }
    else:
        error_message = (
            f"Not Support connection type '{type(connection).__name__}'. "
            f"Connection type should be in [AzureOpenAIConnection, OpenAIConnection]."
        )
        raise InvalidConnectionTypeError(message=error_message)


def get_open_ai_client_by_connection(connection):
    from openai import AzureOpenAI as AzureOpenAIClient
    from openai import OpenAI as OpenAIClient

    if isinstance(connection, AzureOpenAIConnection):
        client = AzureOpenAIClient(**normalize_connection_config(connection))
    elif isinstance(connection, OpenAIConnection):
        client = OpenAIClient(**normalize_connection_config(connection))
    else:
        error_message = (
            f"Not Support connection type '{type(connection).__name__}' for embedding api. "
            f"Connection type should be in [AzureOpenAIConnection, OpenAIConnection]."
        )
        raise InvalidConnectionTypeError(message=error_message)
    return client


def preprocess_template_string(template_string: str) -> str:
    """Remove the image input decorator from the template string and place the image input in a new line."""
    pattern = re.compile(r"\!\[(\s*image\s*)\]\(\{\{(\s*[^\s{}]+\s*)\}\}\)")

    # Find all matches in the input string
    matches = pattern.findall(template_string)

    # Perform substitutions
    for match in matches:
        original = f"![{match[0]}]({{{{{match[1]}}}}})"
        replacement = f"\n{{{{{match[1]}}}}}\n"
        template_string = template_string.replace(original, replacement)

    return template_string


def add_referenced_images_to_set(value, image_set, image_type):
    if isinstance(value, image_type):
        image_set.add(value)
    elif isinstance(value, list):
        for item in value:
            add_referenced_images_to_set(item, image_set, image_type)
    elif isinstance(value, dict):
        for _, item in value.items():
            add_referenced_images_to_set(item, image_set, image_type)


def find_referenced_image_set(kwargs: dict):
    referenced_images = set()
    try:
        from promptflow.contracts.multimedia import Image

        for _, value in kwargs.items():
            add_referenced_images_to_set(value, referenced_images, Image)
    except ImportError:
        pass
    return referenced_images


class ChatInputList(list):
    """
    ChatInputList is a list of ChatInput objects. It is used to override the __str__ method of list to return a string
    that can be easily parsed as message list.
    """

    def __init__(self, iterable=None):
        super().__init__(iterable or [])

    def __str__(self):
        return "\n".join(map(str, self))


def convert_to_chat_list(obj):
    if isinstance(obj, dict):
        return {key: convert_to_chat_list(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return ChatInputList([convert_to_chat_list(item) for item in obj])
    else:
        return obj


def try_parse_name_and_content(role_prompt):
    # customer can add ## in front of name/content for markdown highlight.
    # and we still support name/content without ## prefix for backward compatibility.
    pattern = r"\n*#{0,2}\s*name:\n+\s*(\S+)\s*\n*#{0,2}\s*content:\n?(.*)"
    match = re.search(pattern, role_prompt, re.DOTALL)
    if match:
        return match.group(1), match.group(2)
    return None


def to_content_str_or_list(chat_str: str, hash2images: Mapping):
    chat_str = chat_str.strip()
    chunks = chat_str.split("\n")
    include_image = False
    result = []
    for chunk in chunks:
        if chunk.strip() in hash2images:
            image_message = {}
            image_message["type"] = "image_url"
            image_url = (
                hash2images[chunk.strip()].source_url if hasattr(hash2images[chunk.strip()], "source_url") else None
            )
            if not image_url:
                image_bs64 = hash2images[chunk.strip()].to_base64()
                image_mine_type = hash2images[chunk.strip()]._mime_type
                image_url = {"url": f"data:{image_mine_type};base64,{image_bs64}"}
            image_message["image_url"] = image_url
            result.append(image_message)
            include_image = True
        elif chunk.strip() == "":
            continue
        else:
            result.append({"type": "text", "text": chunk})
    return result if include_image else chat_str


def validate_role(role: str, valid_roles: List[str] = None):
    if not valid_roles:
        valid_roles = ["assistant", "function", "user", "system"]

    if role not in valid_roles:
        valid_roles_str = ",".join([f"'{role}:\\n'" for role in valid_roles])
        error_message = (
            f"The Chat API requires a specific format for prompt definition, and the prompt should include separate "
            f"lines as role delimiters: {valid_roles_str}. Current parsed role '{role}'"
            f" does not meet the requirement. If you intend to use the Completion API, please select the appropriate"
            f" API type and deployment name. If you do intend to use the Chat API, please refer to the guideline at "
            f"https://aka.ms/pfdoc/chat-prompt or view the samples in our gallery that contain 'Chat' in the name."
        )
        raise ChatAPIInvalidRoleError(message=error_message)


def parse_chat(chat_str, images: List = None, valid_roles: List[str] = None):
    if not valid_roles:
        valid_roles = ["system", "user", "assistant", "function"]

    # openai chat api only supports below roles.
    # customer can add single # in front of role name for markdown highlight.
    # and we still support role name without # prefix for backward compatibility.
    separator = r"(?i)^\s*#?\s*(" + "|".join(valid_roles) + r")\s*:\s*\n"

    images = images or []
    hash2images = {str(x): x for x in images}

    chunks = re.split(separator, chat_str, flags=re.MULTILINE)
    chat_list = []

    for chunk in chunks:
        last_message = chat_list[-1] if len(chat_list) > 0 else None
        if last_message and "role" in last_message and "content" not in last_message:
            parsed_result = try_parse_name_and_content(chunk)
            if parsed_result is None:
                # "name" is required if the role is "function"
                if last_message["role"] == "function":
                    raise ChatAPIFunctionRoleInvalidFormatError(
                        message="Failed to parse function role prompt. Please make sure the prompt follows the "
                        "format: 'name:\\nfunction_name\\ncontent:\\nfunction_content'. "
                        "'name' is required if role is function, and it should be the name of the function "
                        "whose response is in the content. May contain a-z, A-Z, 0-9, and underscores, "
                        "with a maximum length of 64 characters. See more details in "
                        "https://platform.openai.com/docs/api-reference/chat/create#chat/create-name "
                        "or view sample 'How to use functions with chat models' in our gallery."
                    )
                # "name" is optional for other role types.
                else:
                    last_message["content"] = to_content_str_or_list(chunk, hash2images)
            else:
                last_message["name"] = parsed_result[0]
                last_message["content"] = to_content_str_or_list(parsed_result[1], hash2images)
        else:
            if chunk.strip() == "":
                continue
            # Check if prompt follows chat api message format and has valid role.
            # References: https://platform.openai.com/docs/api-reference/chat/create.
            role = chunk.strip().lower()
            validate_role(role, valid_roles=valid_roles)
            new_message = {"role": role}
            chat_list.append(new_message)
    return chat_list


# endregion


def init_executable(*, flow_dag: dict = None, flow_path: Path = None, working_dir: Path = None):
    if flow_dag and flow_path:
        raise ValueError("flow_dag and flow_path cannot be both provided.")
    if not flow_dag and not flow_path:
        raise ValueError("flow_dag or flow_path must be provided.")
    if flow_dag and not working_dir:
        raise ValueError("working_dir must be provided when flow_dag is provided.")

    if flow_path:
        flow_dir, flow_filename = resolve_flow_path(flow_path)
        flow_dag = load_yaml(flow_dir / flow_filename)
        if not working_dir:
            working_dir = flow_dir

    from promptflow.contracts.flow import EagerFlow as ExecutableEagerFlow
    from promptflow.contracts.flow import Flow as ExecutableFlow

    if is_flex_flow(yaml_dict=flow_dag):

        entry = flow_dag.get("entry")
        entry_file = resolve_entry_file(entry=entry, working_dir=working_dir)

        # TODO(2991934): support environment variables here
        meta_dict = generate_flow_meta(
            flow_directory=working_dir,
            source_path=entry_file,
            entry=entry,
            dump=False,
        )
        return ExecutableEagerFlow.deserialize(meta_dict)

    # for DAG flow, use data to init executable to improve performance
    return ExecutableFlow._from_dict(flow_dag=flow_dag, working_dir=working_dir)
