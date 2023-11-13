import functools
import json
import re
import sys
import time

from jinja2 import Template
from openai.error import APIError, OpenAIError, RateLimitError, ServiceUnavailableError, Timeout, APIConnectionError
from promptflow.exceptions import SystemErrorException, UserErrorException
from promptflow.tools.exception import ChatAPIInvalidRole, WrappedOpenAIError, LLMError, JinjaTemplateError, \
    ExceedMaxRetryTimes, ChatAPIInvalidFunctions, FunctionCallNotSupportedInStreamMode, \
    ChatAPIFunctionRoleInvalidFormat
from typing import Set, List, Mapping


class ChatInputList(list):
    """
    ChatInputList is a list of ChatInput objects. It is used to override the __str__ method of list to return a string
    that can be easily parsed as message list.
    """
    def __init__(self, iterable=None):
        super().__init__(iterable or [])

    def __str__(self):
        return "\n".join(map(str, self))


def validate_role(role: str, valid_roles: List[str] = None):
    if not valid_roles:
        valid_roles = ["assistant", "function", "user", "system"]

    if role not in valid_roles:
        valid_roles_str = ','.join([f'\'{role}:\\n\''for role in valid_roles])
        error_message = (
            f"The Chat API requires a specific format for prompt definition, and the prompt should include separate "
            f"lines as role delimiters: {valid_roles_str}. Current parsed role '{role}'"
            f" does not meet the requirement. If you intend to use the Completion API, please select the appropriate"
            f" API type and deployment name. If you do intend to use the Chat API, please refer to the guideline at "
            f"https://aka.ms/pfdoc/chat-prompt or view the samples in our gallery that contain 'Chat' in the name."
        )
        raise ChatAPIInvalidRole(message=error_message)


def validate_functions(functions):
    function_example = json.dumps({
        "name": "function_name",
        "parameters": {
            "type": "object",
            "properties": {
                "parameter_name": {
                    "type": "integer",
                    "description": "parameter_description"
                }
            }
        },
        "description": "function_description"
    })
    common_tsg = f"Here is a valid function example: {function_example}. See more details at " \
                 "https://platform.openai.com/docs/api-reference/chat/create#chat/create-functions " \
                 "or view sample 'How to use functions with chat models' in our gallery."
    if len(functions) == 0:
        raise ChatAPIInvalidFunctions(message=f"functions cannot be an empty list. {common_tsg}")
    else:
        for i, function in enumerate(functions):
            # validate if the function is a dict
            if not isinstance(function, dict):
                raise ChatAPIInvalidFunctions(message=f"function {i} '{function}' is not a dict. {common_tsg}")
            # validate if has required keys
            for key in ["name", "parameters"]:
                if key not in function.keys():
                    raise ChatAPIInvalidFunctions(
                        message=f"function {i} '{function}' does not have '{key}' property. {common_tsg}")
            # validate if the parameters is a dict
            if not isinstance(function["parameters"], dict):
                raise ChatAPIInvalidFunctions(
                    message=f"function {i} '{function['name']}' parameters '{function['parameters']}' "
                            f"should be described as a JSON Schema object. {common_tsg}")
            # validate if the parameters has required keys
            for key in ["type", "properties"]:
                if key not in function["parameters"].keys():
                    raise ChatAPIInvalidFunctions(
                        message=f"function {i} '{function['name']}' parameters '{function['parameters']}' "
                                f"does not have '{key}' property. {common_tsg}")
            # validate if the parameters type is object
            if function["parameters"]["type"] != "object":
                raise ChatAPIInvalidFunctions(
                    message=f"function {i} '{function['name']}' parameters 'type' "
                            f"should be 'object'. {common_tsg}")
            # validate if the parameters properties is a dict
            if not isinstance(function["parameters"]["properties"], dict):
                raise ChatAPIInvalidFunctions(
                    message=f"function {i} '{function['name']}' parameters 'properties' "
                            f"should be described as a JSON Schema object. {common_tsg}")


def try_parse_name_and_content(role_prompt):
    # customer can add ## in front of name/content for markdown highlight.
    # and we still support name/content without ## prefix for backward compatibility.
    pattern = r"\n*#{0,2}\s*name:\n+\s*(\S+)\s*\n*#{0,2}\s*content:\n?(.*)"
    match = re.search(pattern, role_prompt, re.DOTALL)
    if match:
        return match.group(1), match.group(2)
    return None


def parse_chat(chat_str, images: List = None, valid_roles: Set[str] = None):
    if not valid_roles:
        valid_roles = ["system", "user", "assistant", "function"]

    # openai chat api only supports below roles.
    # customer can add single # in front of role name for markdown highlight.
    # and we still support role name without # prefix for backward compatibility.
    separator = r"(?i)^\s*#?\s*(system|user|assistant|function)\s*:\s*\n"

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
                    raise ChatAPIFunctionRoleInvalidFormat(
                        message="Failed to parse function role prompt. Please make sure the prompt follows the "
                                "format: 'name:\\nfunction_name\\ncontent:\\nfunction_content'. "
                                "'name' is required if role is function, and it should be the name of the function "
                                "whose response is in the content. May contain a-z, A-Z, 0-9, and underscores, "
                                "with a maximum length of 64 characters. See more details in "
                                "https://platform.openai.com/docs/api-reference/chat/create#chat/create-name "
                                "or view sample 'How to use functions with chat models' in our gallery.")
                # "name" is optional for other role types.
                else:
                    last_message["content"] = to_content_str_or_list(chunk, hash2images)
            else:
                if last_message["role"] == "function":
                    last_message["name"], last_message["content"] = parsed_result
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


def to_content_str_or_list(chat_str: str, hash2images: Mapping):
    chat_str = chat_str.strip()
    chunks = chat_str.split("\n")
    include_image = False
    result = []
    for chunk in chunks:
        if chunk.strip() in hash2images:
            image_message = {}
            image_message["type"] = "image_url"
            image_url = hash2images[chunk.strip()].source_url \
                if hasattr(hash2images[chunk.strip()], "source_url") else None
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


def handle_openai_error(tries: int = 10, delay: float = 8.0):
    """
    A decorator function that used to handle OpenAI error.
    OpenAI Error falls into retriable vs non-retriable ones.

    For retriable error, the decorator use below parameters to control its retry activity with exponential backoff:
     `tries` : max times for the function invocation, type is int
     'delay': base delay seconds for exponential delay, type is float
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for i in range(tries + 1):
                try:
                    return func(*args, **kwargs)
                except (SystemErrorException, UserErrorException) as e:
                    # Throw inner wrapped exception directly
                    raise e
                except (RateLimitError, ServiceUnavailableError, APIError, Timeout, APIConnectionError) as e:
                    #  Handle retriable exception, please refer to
                    #  https://platform.openai.com/docs/guides/error-codes/api-errors
                    #  Use default Timeout 600s, refer to
                    #  https://github.com/openai/openai-python/blob/d1c36582e82cfa97568d7e9184454ee3b77975fc/openai/api_requestor.py#L37  # noqa
                    print(f"Exception occurs: {type(e).__name__}: {str(e)}", file=sys.stderr)
                    if isinstance(e, RateLimitError) and getattr(e.error, "type", None) == "insufficient_quota":
                        # Exit retry if this is quota insufficient error
                        print(f"{type(e).__name__} with insufficient quota. Throw user error.", file=sys.stderr)
                        raise WrappedOpenAIError(e)
                    if isinstance(e, APIConnectionError) and "connection aborted" not in str(e).lower():
                        raise WrappedOpenAIError(e)
                    if i == tries:
                        # Exit retry if max retry reached
                        print(f"{type(e).__name__} reached max retry. Exit retry with user error.", file=sys.stderr)
                        raise ExceedMaxRetryTimes(e)
                    retry_after_in_header = e.headers.get("Retry-After", None)
                    if not retry_after_in_header:
                        retry_after_seconds = delay * (2 ** i)
                        msg = (
                            f"{type(e).__name__} #{i}, but no Retry-After header, "
                            + f"Back off {retry_after_seconds} seconds for retry."
                        )
                        print(msg, file=sys.stderr)
                    else:
                        retry_after_seconds = float(retry_after_in_header) * (2 ** i)
                        msg = (
                            f"{type(e).__name__} #{i}, Retry-After={retry_after_in_header}, "
                            f"Back off {retry_after_seconds} seconds for retry."
                        )
                        print(msg, file=sys.stderr)
                    time.sleep(retry_after_seconds)
                except OpenAIError as e:
                    # For other non-retriable errors from OpenAIError,
                    # For example, AuthenticationError, APIConnectionError, InvalidRequestError, InvalidAPIType
                    # Mark UserError for all the non-retriable OpenAIError
                    print(f"Exception occurs: {type(e).__name__}: {str(e)}", file=sys.stderr)
                    raise WrappedOpenAIError(e)
                except Exception as e:
                    print(f"Exception occurs: {type(e).__name__}: {str(e)}", file=sys.stderr)
                    error_message = f"OpenAI API hits exception: {type(e).__name__}: {str(e)}"
                    raise LLMError(message=error_message)

        return wrapper

    return decorator


def to_bool(value) -> bool:
    return str(value).lower() == "true"


def render_jinja_template(prompt, trim_blocks=True, keep_trailing_newline=True, **kwargs):
    try:
        return Template(prompt, trim_blocks=trim_blocks, keep_trailing_newline=keep_trailing_newline).render(**kwargs)
    except Exception as e:
        # For exceptions raised by jinja2 module, mark UserError
        print(f"Exception occurs: {type(e).__name__}: {str(e)}", file=sys.stderr)
        error_message = f"Failed to render jinja template: {type(e).__name__}: {str(e)}. " \
                        + "Please modify your prompt to fix the issue."
        raise JinjaTemplateError(message=error_message) from e


def process_function_call(function_call):
    if function_call is None:
        param = "auto"
    elif function_call == "auto" or function_call == "none":
        param = function_call
    else:
        function_call_example = json.dumps({"name": "function_name"})
        common_tsg = f"Here is a valid example: {function_call_example}. See the guide at " \
                     "https://platform.openai.com/docs/api-reference/chat/create#chat/create-function_call " \
                     "or view sample 'How to call functions with chat models' in our gallery."
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


def post_process_chat_api_response(completion, stream, functions):
    if stream:
        if functions is not None:
            error_message = "Function calling has not been supported by stream mode yet."
            raise FunctionCallNotSupportedInStreamMode(message=error_message)

        def generator():
            for chunk in completion:
                if chunk.choices:
                    yield getattr(chunk.choices[0]["delta"], "content", "")

        # We must return the generator object, not using yield directly here.
        # Otherwise, the function itself will become a generator, despite whether stream is True or False.
        return generator()
    else:
        # When calling function, function_call response will be returned as a field in message, so we need return
        # message directly. Otherwise, we only return content.
        if functions is not None:
            return completion.choices[0].message
        else:
            # chat api may return message with no content.
            return getattr(completion.choices[0].message, "content", "")


def preprocess_template_string(template_string: str) -> str:
    """Remove the image input decorator from the template string and place the image input in a new line."""
    pattern = re.compile(r'\!\[(\s*image\s*)\]\(\{\{(\s*[^\s{}]+\s*)\}\}\)')

    # Find all matches in the input string
    matches = pattern.findall(template_string)

    # Perform substitutions
    for match in matches:
        original = f"![{match[0]}]({{{{{match[1]}}}}})"
        replacement = f"\n{{{{{match[1]}}}}}\n"
        template_string = template_string.replace(original, replacement)

    return template_string


def convert_to_chat_list(obj):
    if isinstance(obj, dict):
        return {key: convert_to_chat_list(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return ChatInputList([convert_to_chat_list(item) for item in obj])
    else:
        return obj


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
