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
from typing import Set


def validate_role(role: str, valid_roles: Set[str] = None):
    if not valid_roles:
        valid_roles = {"system", "user", "assistant", "function"}

    if role not in valid_roles:
        valid_roles_str = ','.join(sorted([f'\'{role}:\\n\''for role in valid_roles]))
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


def parse_function_role_prompt(function_str):
    # customer can add ## in front of name/content for markdown highlight.
    # and we still support name/content without ## prefix for backward compatibility.
    pattern = r"\n*#{0,2}\s*name:\n\s*(\S+)\s*\n*#{0,2}\s*content:\n(.*)"
    match = re.search(pattern, function_str, re.DOTALL)
    if match:
        return match.group(1), match.group(2)
    else:
        raise ChatAPIFunctionRoleInvalidFormat(
            message="Failed to parse function role prompt. Please make sure the prompt follows the "
                    "format: 'name:\\nfunction_name\\ncontent:\\nfunction_content'. 'name' is required if role is "
                    "function, and it should be the name of the function whose response is in the content. May "
                    "contain a-z, A-Z, 0-9, and underscores, with a maximum length of 64 characters. See more details"
                    " in https://platform.openai.com/docs/api-reference/chat/create#chat/create-name or view sample"
                    " 'How to use functions with chat models' in our gallery.")


def parse_chat(chat_str):
    # openai chat api only supports below roles.
    # customer can add single # in front of role name for markdown highlight.
    # and we still support role name without # prefix for backward compatibility.
    separator = r"(?i)\n+\s*#?\s*(system|user|assistant|function)\s*:\s*\n"
    # Add a newline at the beginning to ensure consistent formatting of role lines.
    # extra new line is removed when appending to the chat list.
    chunks = re.split(separator, '\n'+chat_str)
    chat_list = []
    for chunk in chunks:
        last_message = chat_list[-1] if len(chat_list) > 0 else None
        if last_message and "role" in last_message and "content" not in last_message:
            if last_message["role"] == "function":
                last_message["name"], last_message["content"] = parse_function_role_prompt(chunk)
            else:
                last_message["content"] = chunk
        else:
            if chunk.strip() == "":
                continue
            # Check if prompt follows chat api message format and has valid role.
            # References: https://platform.openai.com/docs/api-reference/chat/create.
            role = chunk.strip().lower()
            validate_role(role)
            new_message = {"role": role}
            chat_list.append(new_message)
    return chat_list


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
