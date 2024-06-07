import copy
import functools
import json
import os
import re
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import List, Mapping

import tiktoken
from openai import APIConnectionError, APIStatusError, APITimeoutError, BadRequestError, OpenAIError, RateLimitError

from promptflow._utils.logger_utils import LoggerFactory
from promptflow._utils.multimedia_utils import MIME_PATTERN, ImageProcessor
from promptflow._utils.yaml_utils import load_yaml
from promptflow.contracts.types import PromptTemplate
from promptflow.core._connection import AzureOpenAIConnection, OpenAIConnection, _Connection
from promptflow.core._errors import (
    ChatAPIFunctionRoleInvalidFormat,
    ChatAPIInvalidFunctions,
    ChatAPIInvalidRoleError,
    ChatAPIInvalidTools,
    ChatAPIToolRoleInvalidFormat,
    CoreError,
    ExceedMaxRetryTimes,
    InvalidOutputKeyError,
    JinjaTemplateError,
    ListDeploymentsError,
    LLMError,
    ParseConnectionError,
    ToolValidationError,
    UnknownConnectionType,
    WrappedOpenAIError,
)
from promptflow.core._model_configuration import ModelConfiguration
from promptflow.core._utils import get_workspace_triad_from_local, render_jinja_template_content
from promptflow.exceptions import SystemErrorException, UserErrorException

logger = LoggerFactory.get_logger(name=__name__)
GPT4V_VERSION = "vision-preview"

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

    if api == "completion":
        rendered_prompt = render_jinja_template_content(
            template_content=prompt, trim_blocks=True, keep_trailing_newline=True, **inputs
        )
    else:
        reference_images = find_referenced_image_set(inputs)
        rendered_prompt = build_messages(prompt=prompt, images=reference_images, **inputs)
    return rendered_prompt


def prepare_open_ai_request_params(model_config, template, connection):
    params = copy.copy(model_config.parameters)
    if isinstance(connection, AzureOpenAIConnection):
        params["extra_headers"] = {"ms-azure-ai-promptflow-called-from": "promptflow-core"}
    params["model"] = model_config._model

    if model_config.api == "completion":
        params["prompt"] = template
    else:
        params["messages"] = template

    # functions and function_call are deprecated and are replaced by tools and tool_choice.
    # if both are provided, tools and tool_choice are used and functions and function_call are ignored.
    if "tools" in params:
        validate_tools(params["tools"])
        params["tool_choice"] = validate_tool_choice(params.get("tool_choice", None))
    else:
        if "functions" in params:
            validate_functions(params["functions"])
            params["function_call"] = validate_function_call(params.get("function_call", None))

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
        # When calling function/tool, function_call/tool_call response will be returned as a field in message,
        # so we need return message directly. Otherwise, we only return content.
        # https://platform.openai.com/docs/api-reference/chat/object#chat/object-choices
        if response.choices[0].finish_reason in ["tool_calls", "function_calls"]:
            response_content = response.model_dump()["choices"][0]["message"]
        else:
            response_content = getattr(response.choices[0].message, "content", "")
        result = format_choice(response_content)
    return result


def num_tokens_from_messages(messages, model, working_dir):
    """Return the number of tokens used by a list of messages."""
    # Ref: https://cookbook.openai.com/examples/how_to_count_tokens_with_tiktoken#6-counting-tokens-for-chat-completions-api-calls  # noqa: E501
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        logger.warning("Model not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")
    if model in {
        "gpt-3.5-turbo-0613",
        "gpt-3.5-turbo-16k-0613",
        "gpt-4-0314",
        "gpt-4-32k-0314",
        "gpt-4-0613",
        "gpt-4-32k-0613",
    }:
        tokens_per_message = 3
        tokens_per_name = 1
    elif model == "gpt-3.5-turbo-0301":
        tokens_per_message = 4  # every message follows <|start|>{role/name}\n{content}<|end|>\n
        tokens_per_name = -1  # if there's a name, the role is omitted
    elif "gpt-3.5-turbo" in model or "gpt-35-turbo":
        logger.warning("gpt-3.5-turbo may update over time. Returning num tokens assuming gpt-3.5-turbo-0613.")
        return num_tokens_from_messages(messages, model="gpt-3.5-turbo-0613", working_dir=working_dir)
    elif "gpt-4" in model:
        logger.warning("gpt-4 may update over time. Returning num tokens assuming gpt-4-0613.")
        return num_tokens_from_messages(messages, model="gpt-4-0613", working_dir=working_dir)
    else:
        raise NotImplementedError(
            f"num_tokens_from_messages() is not implemented for model {model}. "
            "See https://github.com/openai/openai-python/blob/main/chatml.md for information on "
            "how messages are converted to tokens."
        )
    num_tokens = 0
    for message in messages:
        num_tokens += tokens_per_message
        for key, value in message.items():
            if isinstance(value, str):
                num_tokens += len(encoding.encode(value))
            elif isinstance(value, list):
                for item in value:
                    value_type = item.get("type", "text")
                    if value_type == "text":
                        # Calculate content tokens
                        num_tokens += len(encoding.encode(item["text"]))
                    elif value_type == "image_url":
                        image_content = item["image_url"]["url"]
                        if ImageProcessor.is_url(image_content):
                            image_obj = ImageProcessor.create_image_from_url(image_content)
                            num_tokens += _num_tokens_for_image(image_obj.to_base64())
                        elif ImageProcessor.is_base64(image_content):
                            image_obj = ImageProcessor.create_image_from_base64(image_content)
                            num_tokens += _num_tokens_for_image(image_obj.to_base64())
                        else:
                            # Calculate image input as content
                            num_tokens += len(encoding.encode(item["image_url"]["url"]))
            if key == "name":
                num_tokens += tokens_per_name
    num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
    return num_tokens


def _get_image_obj(image_str, working_dir):
    mime_pattern_with_content = MIME_PATTERN.pattern[:-1] + r":\s*(.*)$"
    match = re.match(mime_pattern_with_content, image_str)
    if match:
        mine_type, image_type, image_content = f"image/{match.group(1)}", match.group(2), match.group(3)
        if image_type == "path":
            if not Path(image_content).is_absolute():
                image_content = Path(working_dir) / image_content
            if not Path(image_content).exists():
                logger.warning(f"Cannot find the image path {image_content}, it will be regarded as {type(image_str)}.")
            return ImageProcessor.create_image_from_file(image_content, mine_type)
        elif image_type == "base64":
            return ImageProcessor.create_image_from_base64(image_content, mine_type)
        elif image_type == "url":
            return ImageProcessor.create_image_from_url(image_content, mine_type)
        else:
            logger.warning(f"Invalid mine type {mine_type}, it will be regarded as {type(image_str)}.")
    return image_str


def _num_tokens_for_image(base64_str: str):
    """calculate token of image input"""
    # https://platform.openai.com/docs/guides/vision/calculating-costs
    import base64
    from io import BytesIO
    from math import ceil

    from PIL import Image

    imgdata = base64.b64decode(base64_str)
    image = Image.open(BytesIO(imgdata))
    width, height = image.size
    if width > 2048 or height > 2048:
        aspect_ratio = width / height
        if aspect_ratio > 1:
            width, height = 2048, int(2048 / aspect_ratio)
        else:
            width, height = int(2048 * aspect_ratio), 2048

    if width >= height and height > 768:
        width, height = int((768 / height) * width), 768
    elif height > width and width > 768:
        width, height = 768, int((768 / width) * height)

    tiles_width = ceil(width / 512)
    tiles_height = ceil(height / 512)
    image_tokens = 85 + 170 * (tiles_width * tiles_height)
    return image_tokens


def resolve_references(origin, base_path=None):
    """Resolve all reference in the object."""
    if isinstance(origin, str):
        return resolve_reference(origin, base_path=base_path)
    elif isinstance(origin, list):
        return [resolve_references(item, base_path=base_path) for item in origin]
    elif isinstance(origin, dict):
        return {key: resolve_references(value, base_path=base_path) for key, value in origin.items()}
    else:
        return origin


def resolve_reference(reference, base_path=None):
    """
    Resolve the reference, two types are supported, env, file.
    When the string format is ${env:ENV_NAME}, the environment variable value will be returned.
    When the string format is ${file:file_path}, return the loaded json object.
    """
    pattern = r"\$\{(\w+):(.*)\}"
    match = re.match(pattern, reference)
    if match:
        reference_type, value = match.groups()
        if reference_type == "env":
            return os.environ.get(value, reference)
        elif reference_type == "file":
            if not Path(value).is_absolute() and base_path:
                path = Path(base_path) / value
            else:
                path = Path(value)
            if not path.exists():
                raise UserErrorException(f"Cannot find the reference file {value}.")
            with open(path, "r") as f:
                if path.suffix.lower() == ".json":
                    return json.load(f)
                elif path.suffix.lower() in [".yml", ".yaml"]:
                    return load_yaml(f)
                else:
                    return f.read()
        else:
            logger.warning(f"Unknown reference type {reference_type}, return original value {reference}.")
            return reference
    else:
        return reference


# region: Copied from promptflow-tools


class PromptResult(str):
    """
    PromptResult is the prompt tool output. This class substitutes the initial string output to
    avoid unintended parsing of roles for user input. The class has three properties:
    Original string: the previous rendered prompt result,
    Escaped string: the escaped prompt result string,
    Escaped mapping: the mapping of roles and uuids for the escaped prompt result string.
    """

    def __init__(self, string):
        super().__init__()
        self.original_string = string
        self.escaped_string = ""
        self.escaped_mapping = {}

    def get_escape_string(self) -> str:
        return self.escaped_string

    def set_escape_string(self, escaped_string: str):
        self.escaped_string = escaped_string

    def get_escape_mapping(self) -> dict:
        return self.escaped_mapping

    def set_escape_mapping(self, escape_mapping: dict):
        self.escaped_mapping = escape_mapping

    def need_to_escape(self) -> bool:
        return bool(self.escaped_mapping)

    def merge_escape_mapping_of_prompt_results(self, **kwargs):
        prompt_result_escape_dict = Escaper.merge_escape_mapping_of_prompt_results(**kwargs)
        self.escaped_mapping.update(prompt_result_escape_dict)

    def merge_escape_mapping_of_flow_inputs(self, _inputs_to_escape: list, **kwargs):
        flow_inputs_escape_dict = Escaper.build_flow_inputs_escape_dict(_inputs_to_escape=_inputs_to_escape, **kwargs)
        self.escaped_mapping.update(flow_inputs_escape_dict)


def convert_to_chat_list(obj):
    if isinstance(obj, dict):
        return {key: convert_to_chat_list(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return ChatInputList([convert_to_chat_list(item) for item in obj])
    else:
        return obj


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


def validate_role(role: str, valid_roles: List[str] = None, escape_dict: dict = {}):
    if not valid_roles:
        valid_roles = VALID_ROLES

    if role not in valid_roles:
        valid_roles_str = ",".join([f"'{role}:\\n'" for role in valid_roles])
        # The role string may contain escaped roles(uuids).
        # Need to unescape invalid role as the error message will be displayed to user.
        unescaped_invalid_role = Escaper.unescape_roles(role, escape_dict)
        error_message = (
            f"The Chat API requires a specific format for prompt definition, and the prompt should include separate "
            f"lines as role delimiters: {valid_roles_str}. Current parsed role '{unescaped_invalid_role}'"
            f" does not meet the requirement. If you intend to use the Completion API, please select the appropriate"
            f" API type and deployment name. If you do intend to use the Chat API, please refer to the guideline at "
            f"https://aka.ms/pfdoc/chat-prompt or view the samples in our gallery that contain 'Chat' in the name."
        )
        raise ChatAPIInvalidRoleError(message=error_message)


def try_parse_name_and_content(role_prompt):
    # customer can add ## in front of name/content for markdown highlight.
    # and we still support name/content without ## prefix for backward compatibility.
    pattern = r"\n*#{0,2}\s*name\s*:\s*\n+\s*(\S+)\s*\n*#{0,2}\s*content\s*:\s*\n?(.*)"
    match = re.search(pattern, role_prompt, re.DOTALL)
    if match:
        return match.group(1), match.group(2)
    return None


def try_parse_tool_call_id_and_content(role_prompt):
    # customer can add ## in front of tool_call_id/content for markdown highlight.
    # and we still support tool_call_id/content without ## prefix for backward compatibility.
    pattern = r"\n*#{0,2}\s*tool_call_id\s*:\s*\n+\s*(\S+)\s*\n*#{0,2}\s*content\s*:\s*\n?(.*)"
    match = re.search(pattern, role_prompt, re.DOTALL)
    if match:
        return match.group(1), match.group(2)
    return None


def try_parse_tool_calls(role_prompt):
    # customer can add ## in front of tool_calls for markdown highlight.
    # and we still support tool_calls without ## prefix for backward compatibility.
    pattern = r"\n*#{0,2}\s*tool_calls\s*:\s*\n+\s*(\[.*?\])"
    match = re.search(pattern, role_prompt, re.DOTALL)
    if match:
        try:
            parsed_array = eval(match.group(1))
            return parsed_array
        except Exception:
            None
    return None


def is_tool_chunk(last_message):
    return last_message and "role" in last_message and last_message["role"] == "tool" and "content" not in last_message


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


def parse_chat(
    chat_str,
    images: List = None,
    valid_roles: List[str] = None,
    image_detail: str = "auto",
    escape_dict: dict = {},
):
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
        if is_tool_chunk(last_message):
            parse_tools(last_message, chunk, hash2images, image_detail)
            continue

        if last_message and "role" in last_message and last_message["role"] == "assistant":
            parsed_result = try_parse_tool_calls(chunk)
            if parsed_result is not None:
                last_message["tool_calls"] = parsed_result
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
            validate_role(role, valid_roles=valid_roles, escape_dict=escape_dict)
            new_message = {"role": role}
            chat_list.append(new_message)
    return chat_list


def render_jinja_template(prompt, trim_blocks=True, keep_trailing_newline=True, escape_dict={}, **kwargs):
    try:
        return render_jinja_template_content(
            prompt, trim_blocks=trim_blocks, keep_trailing_newline=keep_trailing_newline, **kwargs
        )
    except Exception as e:
        # For exceptions raised by jinja2 module, mark UserError
        exception_message = str(e)
        unescaped_exception_message = Escaper.unescape_roles(exception_message, escape_dict)
        error_message = (
            f"Failed to render jinja template: {type(e).__name__}: {unescaped_exception_message}. "
            + "Please modify your prompt to fix the issue."
        )
        raise JinjaTemplateError(message=error_message) from e


class Escaper:
    """
    This class handles common escape and unescape functionality for flow inputs and prompt result input.
    Its primary purpose is to avoid unintended parsing of roles for user input.
    """

    @staticmethod
    def merge_escape_mapping_of_prompt_results(**kwargs):
        escape_dict = {}
        for _, v in kwargs.items():
            if isinstance(v, PromptResult) and v.need_to_escape():
                escape_dict.update(v.get_escape_mapping())
        return escape_dict

    @staticmethod
    def build_flow_inputs_escape_dict(_inputs_to_escape: list, **kwargs):
        escape_dict = {}
        if not _inputs_to_escape:
            return escape_dict

        for k, v in kwargs.items():
            if k in _inputs_to_escape:
                escape_dict = Escaper.build_flow_input_escape_dict(v, escape_dict)
        return escape_dict

    @staticmethod
    def build_flow_input_escape_dict(val, escape_dict: dict):
        """
        Build escape dictionary with roles as keys and uuids as values.
        """
        if isinstance(val, ChatInputList):
            for item in val:
                Escaper.build_flow_input_escape_dict(item, escape_dict)
        elif isinstance(val, str):
            pattern = r"(?i)^\s*#?\s*(" + "|".join(VALID_ROLES) + r")\s*:\s*\n"
            roles = re.findall(pattern, val, flags=re.MULTILINE)
            for role in roles:
                if role not in escape_dict.values():
                    # We cannot use a hard-coded hash str for each role, as the same role might be in various case.
                    # For example, the 'system' role may vary in input as 'system', 'System', 'SysteM','SYSTEM', etc.
                    # To convert the escaped roles back to original str, we need to use different uuids for each case.
                    #
                    # Besides, use a uuid as KEY to be able to convert all the escape string back to original role.
                    # For example:
                    #  prompt result 1 escape mapping: {'syStem': 'uuid1'}, escape string: 'uuid1'
                    #  prompt result 2 escape mapping: {'syStem': 'uuid2'}, escape string: 'uuid2'
                    # In order to convert both uuid1 and uuid2 back, we need to store both uuid1 and uuid2.
                    # Otherwise if using role as key, the merged dict would be {'syStem': 'uuid2'}.
                    # So it cannot convert prompt result 2 escape string back.
                    #
                    # Despite the chance of two uuids clashing is extremely low, if it happens, when merge escape dict,
                    # the latter uuid will overwrite the previous one.
                    escape_dict[str(uuid.uuid4())] = role

        return escape_dict

    @staticmethod
    def escape_roles_in_flow_input(val, escape_dict: dict):
        """
        Escape the roles in the prompt inputs to avoid the input string with pattern '# role' get parsed.
        """
        if not escape_dict:
            return val

        if isinstance(val, ChatInputList):
            return ChatInputList([Escaper.escape_roles_in_flow_input(item, escape_dict) for item in val])
        elif isinstance(val, str):
            for encoded_role, role in escape_dict.items():
                val = val.replace(role, encoded_role)
            return val
        else:
            return val

    @staticmethod
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
        if not escape_dict:
            return val

        if isinstance(val, str):
            for encoded_role, role in escape_dict.items():
                val = val.replace(encoded_role, role)
            return val
        elif isinstance(val, list):
            for index, item in enumerate(val):
                if isinstance(item, dict) and "text" in item:
                    for encoded_role, role in escape_dict.items():
                        val[index]["text"] = item["text"].replace(encoded_role, role)
            return val
        else:
            return val

    @staticmethod
    def escape_kwargs(escape_dict: dict, _inputs_to_escape: list, **kwargs):
        # Use escape/unescape to avoid unintended parsing of role in user inputs.
        # There are two scenarios to consider for llm/prompt tool:
        # 1. Prompt injection directly from flow input.
        # 2. Prompt injection from the previous linked prompt tool, where its output becomes llm/prompt input.
        updated_kwargs = {}
        for k, v in kwargs.items():
            if isinstance(v, PromptResult) and v.need_to_escape():
                updated_kwargs[k] = v.get_escape_string()
            elif _inputs_to_escape and k in _inputs_to_escape:
                updated_kwargs[k] = Escaper.escape_roles_in_flow_input(v, escape_dict)
            else:
                updated_kwargs[k] = v

        return updated_kwargs

    @staticmethod
    def build_escape_dict_from_kwargs(_inputs_to_escape: list, **kwargs):
        prompt_result_escape_dict = Escaper.merge_escape_mapping_of_prompt_results(**kwargs)
        flow_inputs_escape_dict = Escaper.build_flow_inputs_escape_dict(_inputs_to_escape=_inputs_to_escape, **kwargs)
        escape_dict = {**prompt_result_escape_dict, **flow_inputs_escape_dict}

        return escape_dict


def build_messages(
    prompt: PromptTemplate,
    images: List = None,
    image_detail: str = "auto",
    **kwargs,
):
    # TODO: Support when prompty is used in flow, escape the flow input. Get escape list from _inputs_to_escape.
    inputs_to_escape = list(kwargs.keys())
    escape_dict = Escaper.build_escape_dict_from_kwargs(_inputs_to_escape=inputs_to_escape, **kwargs)
    updated_kwargs = Escaper.escape_kwargs(escape_dict=escape_dict, _inputs_to_escape=inputs_to_escape, **kwargs)

    # keep_trailing_newline=True is to keep the last \n in the prompt to avoid converting "user:\t\n" to "user:".
    chat_str = render_jinja_template(
        prompt, trim_blocks=True, keep_trailing_newline=True, escape_dict=escape_dict, **updated_kwargs
    )
    messages = parse_chat(chat_str, images=images, image_detail=image_detail, escape_dict=escape_dict)

    if escape_dict and isinstance(messages, list):
        for message in messages:
            if not isinstance(message, dict):
                continue
            for key, val in message.items():
                message[key] = Escaper.unescape_roles(val, escape_dict)

    return messages


def generate_retry_interval(retry_count: int) -> float:
    min_backoff_in_sec = 3
    max_backoff_in_sec = 60
    retry_interval = min_backoff_in_sec + ((2**retry_count) - 1)

    if retry_interval > max_backoff_in_sec:
        retry_interval = max_backoff_in_sec
    return retry_interval


def _parse_resource_id(resource_id):
    # Resource id is connection's id in following format:
    # "/subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.CognitiveServices/accounts/{account}"
    split_parts = resource_id.split("/")
    if len(split_parts) != 9:
        raise ParseConnectionError(f"Connection resourceId format invalid, cur resourceId is {resource_id}.")
    sub, rg, account = split_parts[2], split_parts[4], split_parts[-1]

    return sub, rg, account


def _get_credential():
    from azure.ai.ml._azure_environments import AzureEnvironments, EndpointURLS, _get_cloud, _get_default_cloud_name
    from azure.identity import DefaultAzureCredential

    # Support sovereign cloud cases, like mooncake, fairfax.
    cloud_name = _get_default_cloud_name()
    if cloud_name != AzureEnvironments.ENV_DEFAULT:
        cloud = _get_cloud(cloud=cloud_name)
        authority = cloud.get(EndpointURLS.ACTIVE_DIRECTORY_ENDPOINT)
        credential = DefaultAzureCredential(authority=authority, exclude_shared_token_cache_credential=True)
    else:
        credential = DefaultAzureCredential()

    return credential


def get_workspace_triad():
    # If flow is submitted from cloud, runtime will save the workspace triad to environment
    if (
        "AZUREML_ARM_SUBSCRIPTION" in os.environ
        and "AZUREML_ARM_RESOURCEGROUP" in os.environ
        and "AZUREML_ARM_WORKSPACE_NAME" in os.environ
    ):
        return (
            os.environ["AZUREML_ARM_SUBSCRIPTION"],
            os.environ["AZUREML_ARM_RESOURCEGROUP"],
            os.environ["AZUREML_ARM_WORKSPACE_NAME"],
        )
    else:
        # If flow is submitted from local, it will get workspace triad from your azure cloud config file
        # If this config file isn't set up, it will return None.
        return get_workspace_triad_from_local()


def list_deployment_connections(
    subscription_id=None,
    resource_group_name=None,
    workspace_name=None,
    connection="",
):
    try:
        # Do not support dynamic list if azure packages are not installed.
        from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient

        from promptflow.azure.operations._arm_connection_operations import (
            ArmConnectionOperations,
            OpenURLFailedUserError,
        )
    except ImportError:
        return None

    # Do not support dynamic list if the workspace triple is set in the local.
    if not subscription_id or not resource_group_name or not workspace_name:
        return None

    try:
        credential = _get_credential()
        try:
            # Currently, the param 'connection' is str, not AzureOpenAIConnection type.
            conn = ArmConnectionOperations._build_connection_dict(
                name=connection,
                subscription_id=subscription_id,
                resource_group_name=resource_group_name,
                workspace_name=workspace_name,
                credential=credential,
            )
            resource_id = conn.get("value").get("resource_id", "")
            if not resource_id:
                return None
            conn_sub, conn_rg, conn_account = _parse_resource_id(resource_id)
        except OpenURLFailedUserError:
            return None
        except ListDeploymentsError as e:
            raise e
        except Exception as e:
            msg = f"Parsing connection with exception: {e}"
            raise ListDeploymentsError(msg=msg) from e

        client = CognitiveServicesManagementClient(
            credential=credential,
            subscription_id=conn_sub,
        )
        return client.deployments.list(
            resource_group_name=conn_rg,
            account_name=conn_account,
        )
    except Exception as e:
        if hasattr(e, "status_code") and e.status_code == 403:
            msg = f"Failed to list deployments due to permission issue: {e}"
            raise ListDeploymentsError(msg=msg) from e
        else:
            msg = f"Failed to list deployments with exception: {e}"
            raise ListDeploymentsError(msg=msg) from e


def is_retriable_api_connection_error(e: APIConnectionError):
    retriable_error_messages = [
        "connection aborted",
        # issue 2296
        "server disconnected without sending a response",
    ]
    for message in retriable_error_messages:
        if message in str(e).lower() or message in str(e.__cause__).lower():
            return True

    return False


def handle_openai_error(tries: int = 10, unprocessable_entity_error_tries: int = 3):
    """
    A decorator function for handling OpenAI errors.

    OpenAI errors are categorized into retryable and non-retryable.
    For retryable errors, the default is to retry 10 times. The waiting time for each round of retry
    increases exponentially, with a maximum waiting time of 60 seconds.
    The total waiting time for retrying 10 times is about 400s

    For retryable errors, the decorator uses the following parameters to control its retry behavior:
    `tries`: max times for the function invocation, type is int
    `unprocessable_entity_error_tries`: max times for the function invocation when consecutive
        422 error occurs, type is int

    Note:
    - The retry policy for UnprocessableEntityError is different because retrying may not be beneficial,
      so small threshold and requiring consecutive errors.
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            consecutive_422_error_count = 0
            for i in range(tries + 1):
                try:
                    return func(*args, **kwargs)
                except (SystemErrorException, UserErrorException) as e:
                    # Throw inner wrapped exception directly
                    raise e
                except (APIStatusError, APIConnectionError) as e:
                    #  Handle retriable exception, please refer to
                    #  https://platform.openai.com/docs/guides/error-codes/api-errors
                    logger.error(f"Exception occurs: {type(e).__name__}: {str(e)}")
                    # Firstly, exclude some non-retriable errors.
                    # Vision model does not support all chat api parameters, e.g. response_format and function_call.
                    # Related issue https://github.com/microsoft/promptflow/issues/1683
                    if isinstance(e, BadRequestError):
                        raise WrappedOpenAIError(e)

                    if (
                        isinstance(e, APIConnectionError)
                        and not isinstance(e, APITimeoutError)
                        and not is_retriable_api_connection_error(e)
                    ):
                        raise WrappedOpenAIError(e)

                    # Retry InternalServerError(>=500), RateLimitError(429), UnprocessableEntityError(422)
                    # Solution references:
                    # https://platform.openai.com/docs/guides/error-codes/api-errors
                    # https://platform.openai.com/docs/guides/error-codes/python-library-error-types
                    if isinstance(e, APIStatusError):
                        status_code = e.response.status_code
                        if status_code < 500 and status_code not in [429, 422]:
                            raise WrappedOpenAIError(e)
                    if isinstance(e, RateLimitError) and getattr(e, "type", None) == "insufficient_quota":
                        # Exit retry if this is quota insufficient error
                        logger.error(f"{type(e).__name__} with insufficient quota. Throw user error.")
                        raise WrappedOpenAIError(e)

                    # Retriable errors.
                    # To fix issue #2296, retry on api connection error, but with a separate retry policy.
                    if isinstance(e, APIStatusError) and e.response.status_code == 422:
                        consecutive_422_error_count += 1
                    else:
                        # If other retriable errors, reset consecutive_422_error_count.
                        consecutive_422_error_count = 0

                    if i == tries or consecutive_422_error_count == unprocessable_entity_error_tries:
                        # Exit retry if max retry reached
                        logger.error(f"{type(e).__name__} reached max retry. Exit retry with user error.")
                        raise ExceedMaxRetryTimes(e)

                    if hasattr(e, "response") and e.response is not None:
                        retry_after_in_header = e.response.headers.get("retry-after", None)
                    else:
                        retry_after_in_header = None

                    if not retry_after_in_header:
                        retry_after_seconds = generate_retry_interval(i)
                        msg = (
                            f"{type(e).__name__} #{i}, but no Retry-After header, "
                            + f"Back off {retry_after_seconds} seconds for retry."
                        )
                        logger.warning(msg)
                    else:
                        retry_after_seconds = float(retry_after_in_header)
                        msg = (
                            f"{type(e).__name__} #{i}, Retry-After={retry_after_in_header}, "
                            f"Back off {retry_after_seconds} seconds for retry."
                        )
                        logger.warning(msg)
                    time.sleep(retry_after_seconds)
                except OpenAIError as e:
                    # For other non-retriable errors from OpenAIError,
                    # For example, AuthenticationError, APIConnectionError, BadRequestError, NotFoundError
                    # Mark UserError for all the non-retriable OpenAIError
                    logger.error(f"Exception occurs: {type(e).__name__}: {str(e)}")
                    raise WrappedOpenAIError(e)
                except Exception as e:
                    logger.error(f"Exception occurs: {type(e).__name__}: {str(e)}")
                    error_message = f"OpenAI API hits exception: {type(e).__name__}: {str(e)}"
                    raise LLMError(message=error_message)

        return wrapper

    return decorator


def validate_function(common_tsg, i, function, expection: ToolValidationError):
    # validate if the function is a dict
    if not isinstance(function, dict):
        raise expection(message=f"function {i} '{function}' is not a dict. {common_tsg}")
    # validate if has required keys
    for key in ["name", "parameters"]:
        if key not in function.keys():
            raise expection(message=f"function {i} '{function}' does not have '{key}' property. {common_tsg}")
    # validate if the parameters is a dict
    if not isinstance(function["parameters"], dict):
        raise expection(
            message=f"function {i} '{function['name']}' parameters '{function['parameters']}' "
            f"should be described as a JSON Schema object. {common_tsg}"
        )
    # validate if the parameters has required keys
    for key in ["type", "properties"]:
        if key not in function["parameters"].keys():
            raise expection(
                message=f"function {i} '{function['name']}' parameters '{function['parameters']}' "
                f"does not have '{key}' property. {common_tsg}"
            )
    # validate if the parameters type is object
    if function["parameters"]["type"] != "object":
        raise expection(
            message=f"function {i} '{function['name']}' parameters 'type' " f"should be 'object'. {common_tsg}"
        )
    # validate if the parameters properties is a dict
    if not isinstance(function["parameters"]["properties"], dict):
        raise expection(
            message=f"function {i} '{function['name']}' parameters 'properties' "
            f"should be described as a JSON Schema object. {common_tsg}"
        )


def validate_functions(functions):
    function_example = json.dumps(
        {
            "name": "function_name",
            "parameters": {
                "type": "object",
                "properties": {"parameter_name": {"type": "integer", "description": "parameter_description"}},
            },
            "description": "function_description",
        }
    )
    common_tsg = (
        f"Here is a valid function example: {function_example}. See more details at "
        "https://platform.openai.com/docs/api-reference/chat/create#chat/create-functions "
        "or view sample 'How to use functions with chat models' in our gallery."
    )
    if len(functions) == 0:
        raise ChatAPIInvalidFunctions(message=f"functions cannot be an empty list. {common_tsg}")
    else:
        for i, function in enumerate(functions):
            validate_function(common_tsg, i, function, ChatAPIInvalidFunctions)


def validate_tools(tools):
    tool_example = json.dumps(
        {
            "type": "function",
            "function": {
                "name": "get_current_weather",
                "description": "Get the current weather in a given location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "The city and state, e.g. San Francisco, CA",
                        },
                        "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
                    },
                    "required": ["location"],
                },
            },
        }
    )
    common_tsg = (
        f"Here is a valid tool example: {tool_example}. See more details at "
        "https://platform.openai.com/docs/api-reference/chat/create"
    )

    if len(tools) == 0:
        raise ChatAPIInvalidTools(message=f"tools cannot be an empty list. {common_tsg}")
    for i, tool in enumerate(tools):
        # validate if the tool is a dict
        if not isinstance(tool, dict):
            raise ChatAPIInvalidTools(message=f"tool {i} '{tool}' is not a dict. {common_tsg}")
        # validate if has required keys
        for key in ["type", "function"]:
            if key not in tool.keys():
                raise ChatAPIInvalidTools(message=f"tool {i} '{tool}' does not have '{key}' property. {common_tsg}")
        validate_function(common_tsg, i, tool["function"], ChatAPIInvalidTools)


def validate_function_call(function_call):
    if function_call is None:
        param = "auto"
    elif function_call == "auto" or function_call == "none":
        param = function_call
    else:
        function_call_example = json.dumps({"name": "function_name"})
        common_tsg = (
            f"Here is a valid example: {function_call_example}. See the guide at "
            "https://platform.openai.com/docs/api-reference/chat/create#chat/create-function_call "
            "or view sample 'How to call functions with chat models' in our gallery."
        )
        param = function_call
        if not isinstance(param, dict):
            raise ChatAPIInvalidFunctions(
                message=f"function_call parameter '{param}' must be a dict, but not {type(function_call)}. {common_tsg}"
            )
        else:
            if "name" not in function_call:
                raise ChatAPIInvalidFunctions(
                    message=f'function_call parameter {json.dumps(param)} must contain "name" field. {common_tsg}'
                )
    return param


def validate_tool_choice(tool_choice):
    if tool_choice is None:
        param = "auto"
    elif tool_choice == "auto" or tool_choice == "none":
        param = tool_choice
    else:
        tool_choice_example = json.dumps({"type": "function", "function": {"name": "my_function"}})
        common_tsg = (
            f"Here is a valid example: {tool_choice_example}. See the guide at "
            "https://platform.openai.com/docs/api-reference/chat/create."
        )
        param = tool_choice
        if not isinstance(param, dict):
            raise ChatAPIInvalidTools(
                message=f"tool_choice parameter '{param}' must be a dict, but not {type(tool_choice)}. {common_tsg}"
            )
        else:
            if "type" not in tool_choice:
                raise ChatAPIInvalidTools(
                    message=f'tool_choice parameter {json.dumps(param)} must contain "type" field. {common_tsg}'
                )

            if "function" not in tool_choice:
                raise ChatAPIInvalidTools(
                    message=f'tool_choice parameter {json.dumps(param)} must contain "function" field. {common_tsg}'
                )

            if not isinstance(param["function"], dict):
                raise ChatAPIInvalidTools(
                    message=f'function parameter "{param["function"]}" in tool_choice must be a dict, '
                    f'but not {type(param["function"])}. {common_tsg}'
                )
            elif "name" not in tool_choice["function"]:
                raise ChatAPIInvalidTools(
                    message=f'function parameter "{json.dumps(param["function"])}" in tool_choice must '
                    f'contain "name" field. {common_tsg}'
                )
    return param


# endregion
