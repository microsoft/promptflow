import copy
import json
import os
import re
import uuid
from dataclasses import asdict
from typing import List, Mapping

from promptflow.contracts.types import PromptTemplate
from promptflow.core._connection import AzureOpenAIConnection, OpenAIConnection, _Connection
from promptflow.core._errors import (
    ChatAPIInvalidRoleError,
    ChatAPIToolRoleInvalidFormat,
    CoreError,
    InvalidOutputKeyError,
    UnknownConnectionType,
)
from promptflow.core._model_configuration import ModelConfiguration
from promptflow.core._utils import render_jinja_template_content

VALID_ROLES = ["system", "user", "assistant", "function", "tool"]


def update_dict_recursively(origin_dict, overwrite_dict):
    updated_dict = {}
    for k, v in overwrite_dict.items():
        if isinstance(v, dict):
            updated_dict[k] = update_dict_recursively(origin_dict.get(k, {}), v)
        else:
            updated_dict[k] = v
    for k, v in origin_dict.items():
        if k not in updated_dict:
            updated_dict[k] = v
    return updated_dict


def parse_environment_variable(value):
    """Get environment variable from ${env:ENV_NAME}. If not found, return original value."""
    if not isinstance(value, str):
        return value
    pattern = r"^\$\{env:(.*)\}$"
    result = re.match(pattern, value)
    if result:
        env_name = result.groups()[0]
        return os.environ.get(env_name, value)
    else:
        return value


def get_connection_by_name(connection_name):
    try:
        from promptflow._sdk._pf_client import PFClient
    except ImportError as ex:
        raise CoreError(f"Please try 'pip install promptflow-devkit' to install dependency, {ex.msg}")
    client = PFClient()
    connection_obj = client.connections._get(connection_name, with_secrets=True)
    connection = connection_obj._to_execution_connection_dict()["value"]
    connection_type = connection_obj.TYPE
    return connection, connection_type


def is_empty_connection_config(connection_dict):
    reversed_fields = set(["azure_deployment", "model"])
    connection_keys = set([k for k, v in connection_dict.items() if v])
    return len(connection_keys - reversed_fields) == 0


def convert_model_configuration_to_connection(model_configuration):
    if isinstance(model_configuration, dict):
        # Get connection from connection field
        connection = model_configuration.get("connection", None)
        if connection:
            if isinstance(connection, str):
                # Get connection by name
                connection, connection_type = get_connection_by_name(connection)
            elif isinstance(connection, _Connection):
                return connection
        else:
            connection_dict = copy.copy(model_configuration)
            connection_type = connection_dict.pop("type", None)
            # Get value from environment
            connection = {k: parse_environment_variable(v) for k, v in connection_dict.items()}
    elif isinstance(model_configuration, ModelConfiguration):
        # Get connection from model configuration
        connection_type = model_configuration._type
        if model_configuration.connection:
            connection, _ = get_connection_by_name(model_configuration.connection)
        else:
            connection = {k: parse_environment_variable(v) for k, v in asdict(model_configuration).items()}

    if connection_type in [AzureOpenAIConnection.TYPE, "azure_openai"]:
        if "api_base" not in connection:
            connection["api_base"] = connection.get("azure_endpoint", None)
        if is_empty_connection_config(connection):
            return AzureOpenAIConnection.from_env()
        else:
            return AzureOpenAIConnection(**connection)
    elif connection_type in [OpenAIConnection.TYPE, "openai"]:
        if is_empty_connection_config(connection):
            return OpenAIConnection.from_env()
        else:
            return OpenAIConnection(**connection)
    error_message = (
        f"Not Support connection type {connection_type} for embedding api. "
        f"Connection type should be in [{AzureOpenAIConnection.TYPE}, {OpenAIConnection.TYPE}]."
    )
    raise UnknownConnectionType(message=error_message)


def convert_prompt_template(template, inputs, api):
    prompt = preprocess_template_string(template)

    # convert list type into ChatInputList type
    converted_kwargs = convert_to_chat_list(inputs)
    if api == "completion":
        rendered_prompt = render_jinja_template_content(
            template_content=prompt, trim_blocks=True, keep_trailing_newline=True, **converted_kwargs
        )
    else:
        rendered_prompt = build_messages(prompt=prompt, **converted_kwargs)
    return rendered_prompt


def prepare_open_ai_request_params(model_config, template, connection):
    # TODO validate function in params
    params = copy.copy(model_config.parameters)
    if isinstance(connection, AzureOpenAIConnection):
        params["extra_headers"] = {"ms-azure-ai-promptflow-called-from": "promptflow-core"}
    params["model"] = model_config._model

    if model_config.api == "completion":
        params["prompt"] = template
    else:
        params["messages"] = template
    return params


def get_open_ai_client_by_connection(connection, is_async=False):
    from openai import AsyncAzureOpenAI as AsyncAzureOpenAIClient
    from openai import AsyncOpenAI as AsyncOpenAIClient
    from openai import AzureOpenAI as AzureOpenAIClient
    from openai import OpenAI as OpenAIClient

    if isinstance(connection, AzureOpenAIConnection):
        if is_async:
            client = AsyncAzureOpenAIClient(**normalize_connection_config(connection))
        else:
            client = AzureOpenAIClient(**normalize_connection_config(connection))
    elif isinstance(connection, OpenAIConnection):
        if is_async:
            client = AsyncOpenAIClient(**normalize_connection_config(connection))
        else:
            client = OpenAIClient(**normalize_connection_config(connection))
    else:
        error_message = (
            f"Not Support connection type '{type(connection).__name__}' for embedding api. "
            f"Connection type should be in [AzureOpenAIConnection, OpenAIConnection]."
        )
        raise UnknownConnectionType(message=error_message)
    return client


def send_request_to_llm(client, api, parameters):
    if api == "completion":
        result = client.completions.create(**parameters)
    else:
        result = client.chat.completions.create(**parameters)
    return result


def format_llm_response(response, api, is_first_choice, response_format=None, streaming=False, outputs=None):
    """
    Format LLM response

    If is_first_choice is false, it will directly return LLM response.
    If is_first_choice is true, behavior as blow:
        response_format: type: text
            - n: None/1/2
                Return the first choice content. Return type is string.
            - stream: True
                Return generator list of first choice content. Return type is generator[str]
        response_format: type: json_object
            - n : None/1/2
                Return json dict of the first choice. Return type is dict
            - stream: True
                Return json dict of the first choice. Return type is dict
            - outputs
                Extract corresponding output in the json dict to the first choice. Return type is dict.

    :param response: LLM response.
    :type response:
    :param api: API type of the LLM.
    :type api: str
    :param is_first_choice: If true, it will return the first item in response choices, else it will return all response
    :type is_first_choice: bool
    :param response_format: An object specifying the format that the model must output.
    :type response_format: str
    :param streaming: Indicates whether to stream the response
    :type streaming: bool
    :param outputs: Extract corresponding output in json format response
    :type outputs: dict
    :return: Formatted LLM response.
    :rtype: Union[str, dict, Response]
    """

    def format_choice(item):
        # response_format is one of text or json_object.
        # https://platform.openai.com/docs/api-reference/chat/create#chat-create-response_format
        if is_json_format:
            result_dict = json.loads(item)
            if not outputs:
                return result_dict
            # return the keys in outputs
            output_results = {}
            for key in outputs:
                if key not in result_dict:
                    raise InvalidOutputKeyError(f"Cannot find {key} in response {list(result_dict.keys())}")
                output_results[key] = result_dict[key]
            return output_results
        # Return text format response
        return item

    def format_stream(llm_response):
        cur_index = None
        for chunk in llm_response:
            if len(chunk.choices) > 0 and chunk.choices[0].delta.content:
                if cur_index is None:
                    cur_index = chunk.choices[0].index
                if cur_index != chunk.choices[0].index:
                    return
                yield chunk.choices[0].delta.content

    if not is_first_choice:
        return response

    is_json_format = isinstance(response_format, dict) and response_format.get("type", None) == "json_object"
    if streaming:
        if not is_json_format:
            return format_stream(llm_response=response)
        else:
            content = "".join([item for item in format_stream(llm_response=response)])
            return format_choice(content)
    if api == "completion":
        result = format_choice(response.choices[0].text)
    else:
        result = format_choice(getattr(response.choices[0].message, "content", ""))
    return result


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
        raise UnknownConnectionType(message=error_message)


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


def to_content_str_or_list(chat_str: str, hash2images: Mapping, image_detail: str):
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
                image_url = f"data:{image_mine_type};base64,{image_bs64}"
            image_message["image_url"] = {"url": image_url, "detail": image_detail}
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


def is_tools_chunk(last_message):
    return last_message and "role" in last_message and last_message["role"] == "tool" and "content" not in last_message


def is_assistant_tool_calls_chunk(last_message, chunk):
    return last_message and "role" in last_message and last_message["role"] == "assistant" and "tool_calls" in chunk


def parse_tool_calls_for_assistant(last_message, chunk):
    parsed_result = try_parse_tool_calls(chunk)
    error_msg = "Failed to parse assistant role prompt with tool_calls. Please make sure the prompt follows the format:"
    " 'tool_calls:\\n[{ id: tool_call_id, type: tool_type, function: {name: function_name, arguments: function_args }]'"
    "See more details in https://platform.openai.com/docs/api-reference/chat/create#chat-create-messages"

    if parsed_result is None:
        raise ChatAPIAssistantRoleInvalidFormat(message=error_msg)
    else:
        parsed_array = None
        try:
            parsed_array = eval(parsed_result)
            last_message["tool_calls"] = parsed_array
        except Exception:
            raise ChatAPIAssistantRoleInvalidFormat(message=error_msg)


def parse_tools(last_message, chunk, hash2images, image_detail):
    parsed_result = try_parse_tool_call_id_and_content(chunk)
    if parsed_result is None:
        raise ChatAPIToolRoleInvalidFormat(
            message="Failed to parse tool role prompt. Please make sure the prompt follows the "
            "format: 'tool_call_id:\\ntool_call_id\\ncontent:\\ntool_content'. "
            "'tool_call_id' is required if role is tool, and it should be the tool call that this message is responding"
            " to. See more details in https://platform.openai.com/docs/api-reference/chat/create#chat-create-messages"
        )
    else:
        last_message["tool_call_id"] = parsed_result[0]
        last_message["content"] = to_content_str_or_list(parsed_result[1], hash2images, image_detail)


def parse_chat(chat_str, images: List = None, valid_roles: List[str] = None, image_detail: str = "auto"):
    if not valid_roles:
        valid_roles = VALID_ROLES

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
        if is_tools_chunk(last_message):
            parse_tools(last_message, chunk, hash2images, image_detail)
            continue

        if is_assistant_tool_calls_chunk(last_message, chunk):
            parse_tool_calls_for_assistant(last_message, chunk)
            continue

        if (
            last_message
            and "role" in last_message
            and "content" not in last_message
            and "tool_calls" not in last_message
        ):
            parsed_result = try_parse_name_and_content(chunk)
            if parsed_result is None:
                # "name" is required if the role is "function"
                if last_message["role"] == "function":
                    raise ChatAPIFunctionRoleInvalidFormat(
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
                    last_message["content"] = to_content_str_or_list(chunk, hash2images, image_detail)
            else:
                last_message["name"] = parsed_result[0]
                last_message["content"] = to_content_str_or_list(parsed_result[1], hash2images, image_detail)
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


def build_escape_dict(kwargs: dict):
    escape_dict = {}
    for _, value in kwargs.items():
        escape_dict = _build_escape_dict(value, escape_dict)
    return escape_dict


def _build_escape_dict(val, escape_dict: dict):
    """
    Build escape dictionary with roles as keys and uuids as values.
    """
    if isinstance(val, ChatInputList):
        for item in val:
            _build_escape_dict(item, escape_dict)
    elif isinstance(val, str):
        pattern = r"(?i)^\s*#?\s*(" + "|".join(VALID_ROLES) + r")\s*:\s*\n"
        roles = re.findall(pattern, val, flags=re.MULTILINE)
        for role in roles:
            if role not in escape_dict:
                # We cannot use a hard-coded hash str for each role, as the same role might be in various case formats.
                # For example, the 'system' role may vary in input as 'system', 'System', 'SysteM','SYSTEM', etc.
                # To convert the escaped roles back to the original str, we need to use different uuids for each case.
                escape_dict[role] = str(uuid.uuid4())

    return escape_dict


def escape_roles(val, escape_dict: dict):
    """
    Escape the roles in the prompt inputs to avoid the input string with pattern '# role' get parsed.
    """
    if isinstance(val, ChatInputList):
        return ChatInputList([escape_roles(item, escape_dict) for item in val])
    elif isinstance(val, str):
        for role, encoded_role in escape_dict.items():
            val = val.replace(role, encoded_role)
        return val
    else:
        return val


def unescape_roles(val, escape_dict: dict):
    """
    Unescape the roles in the parsed chat messages to restore the original role names.

    Besides the case that value is: 'some text. escaped_roles (i.e. fake uuids)'
    We also need to handle the vision case that the content is converted to list.
    For example:
        [{
            'type': 'text',
            'text': 'some text. fake_uuid'
        }, {
            'type': 'image_url',
            'image_url': {}
        }]
    """
    if isinstance(val, str):
        for role, encoded_role in escape_dict.items():
            val = val.replace(encoded_role, role)
        return val
    elif isinstance(val, list):
        for index, item in enumerate(val):
            if isinstance(item, dict) and "text" in item:
                for role, encoded_role in escape_dict.items():
                    val[index]["text"] = item["text"].replace(encoded_role, role)
        return val
    else:
        return val


def build_messages(
    prompt: PromptTemplate,
    images: List = None,
    image_detail: str = "auto",
    **kwargs,
):
    # Use escape/unescape to avoid unintended parsing of role in user inputs.
    escape_dict = build_escape_dict(kwargs)
    updated_kwargs = {key: escape_roles(value, escape_dict) for key, value in kwargs.items()}

    # keep_trailing_newline=True is to keep the last \n in the prompt to avoid converting "user:\t\n" to "user:".
    chat_str = render_jinja_template_content(prompt, trim_blocks=True, keep_trailing_newline=True, **updated_kwargs)
    messages = parse_chat(chat_str, images=images, image_detail=image_detail)

    if escape_dict and isinstance(messages, list):
        for message in messages:
            if not isinstance(message, dict):
                continue
            for key, val in message.items():
                message[key] = unescape_roles(val, escape_dict)

    return messages


# endregion
