import copy
import functools
import json
import os
import re
import sys
import time
from dataclasses import asdict
from typing import List, Mapping

from openai import APIConnectionError, APIStatusError, APITimeoutError, BadRequestError, OpenAIError, RateLimitError

from promptflow._utils.logger_utils import LoggerFactory
from promptflow.core._connection import AzureOpenAIConnection, OpenAIConnection, _Connection
from promptflow.core._errors import (
    ChatAPIFunctionRoleInvalidFormatError,
    ChatAPIInvalidRoleError,
    CoreError,
    ExceedMaxRetryTimes,
    InvalidOutputKeyError,
    ListDeploymentsError,
    LLMError,
    ParseConnectionError,
    UnknownConnectionType,
    WrappedOpenAIError,
)
from promptflow.core._model_configuration import ModelConfiguration
from promptflow.core._utils import get_workspace_triad_from_local, render_jinja_template_content
from promptflow.exceptions import SystemErrorException, UserErrorException

logger = LoggerFactory.get_logger(name=__name__)
GPT4V_VERSION = "vision-preview"


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
    rendered_prompt = render_jinja_template_content(
        template_content=prompt, trim_blocks=True, keep_trailing_newline=True, **converted_kwargs
    )
    if api == "completion":
        return rendered_prompt
    else:
        referenced_images = find_referenced_image_set(inputs)
        return parse_chat(rendered_prompt, list(referenced_images))


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


def refine_extra_fields_not_permitted_error(connection, deployment_name, model):
    tsg = (
        "Please kindly avoid using vision model in LLM tool, "
        "because vision model cannot work with some chat api parameters. "
        "You can change to use tool 'Azure OpenAI GPT-4 Turbo with Vision' "
        "or 'OpenAI GPT-4V' for vision model."
    )
    try:
        if isinstance(connection, AzureOpenAIConnection):
            subscription_id, resource_group, workspace_name = get_workspace_triad()
            if subscription_id and resource_group and workspace_name:
                deployment_collection = list_deployment_connections(
                    subscription_id, resource_group, workspace_name, connection.name
                )
                for item in deployment_collection:
                    if deployment_name == item.name:
                        if item.properties.model.version in [GPT4V_VERSION]:
                            return tsg
        elif isinstance(connection, OpenAIConnection) and model in ["gpt-4-vision-preview"]:
            return tsg
    except Exception as e:
        print(
            f"Exception occurs when refine extra fields not permitted error for llm: " f"{type(e).__name__}: {str(e)}",
            file=sys.stderr,
        )

    return None


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
                    print(f"Exception occurs: {type(e).__name__}: {str(e)}", file=sys.stderr)
                    # Firstly, exclude some non-retriable errors.
                    # Vision model does not support all chat api parameters, e.g. response_format and function_call.
                    # Recommend user to use vision model in vision tools, rather than LLM tool.
                    # Related issue https://github.com/microsoft/promptflow/issues/1683
                    if isinstance(e, BadRequestError) and "extra fields not permitted" in str(e).lower():
                        refined_error_message = refine_extra_fields_not_permitted_error(
                            args[0].connection, kwargs.get("deployment_name", ""), kwargs.get("model", "")
                        )
                        if refined_error_message:
                            raise LLMError(message=f"{str(e)} {refined_error_message}")
                        else:
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
                        print(f"{type(e).__name__} with insufficient quota. Throw user error.", file=sys.stderr)
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
                        print(f"{type(e).__name__} reached max retry. Exit retry with user error.", file=sys.stderr)
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
                    print(f"Exception occurs: {type(e).__name__}: {str(e)}", file=sys.stderr)
                    raise WrappedOpenAIError(e)
                except Exception as e:
                    print(f"Exception occurs: {type(e).__name__}: {str(e)}", file=sys.stderr)
                    error_message = f"OpenAI API hits exception: {type(e).__name__}: {str(e)}"
                    raise LLMError(message=error_message)

        return wrapper

    return decorator


# endregion
