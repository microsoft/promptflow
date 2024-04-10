from typing import List, Dict

from promptflow.tools.common import handle_openai_error, _get_credential
from promptflow.tools.exception import InvalidConnectionType
from promptflow.contracts.types import PromptTemplate
from promptflow.tools.aoai import AzureOpenAI
from promptflow.tools.openai import OpenAI

# Avoid circular dependencies: Use import 'from promptflow._internal' instead of 'from promptflow'
# since the code here is in promptflow namespace as well
from promptflow._internal import tool
from promptflow.connections import AzureOpenAIConnection, OpenAIConnection
try:
    from promptflow.connections import ServerlessConnection
except ImportError:
    # If unable to import ServerlessConnection, define a placeholder class to allow isinstance checks to pass.
    # ServerlessConnection was introduced in pf version 1.6.0.
    class ServerlessConnection:
        pass


def get_cloud_connection(connection_name, subscription_id, resource_group_name, workspace_name):
    try:
        # TODO: remove pf-azure dependencies by using ConnectionProvider.get_instance() method.
        credential = _get_credential()
        from promptflow.azure.operations._arm_connection_operations import ArmConnectionOperations

        return ArmConnectionOperations._build_connection_dict(
            name=connection_name,
            subscription_id=subscription_id,
            resource_group_name=resource_group_name,
            workspace_name=workspace_name,
            credential=credential
        )
    except Exception as e:
        print(f"Error getting cloud connection: {e}")
        return None


def get_local_connection(connection_name):
    try:
        # TODO: remove pf-devkit dependencies by using ConnectionProvider.get_instance() method.
        from promptflow import PFClient

        pf = PFClient()
        return pf.connections.get(connection_name)
    except Exception as e:
        print(f"Error getting local connection: {e}")
        return None


# api needs dynamic list because we do not offer "completion" api for serverless connection.
def list_apis(
    subscription_id=None,
    resource_group_name=None,
    workspace_name=None,
    connection_name=""
) -> List[Dict[str, str]]:
    if not connection_name:
        return []

    connection = get_local_connection(connection_name)
    if connection is None:
        connection = get_cloud_connection(connection_name, subscription_id, resource_group_name, workspace_name)

    if connection is None:
        return []

    if (isinstance(connection, dict) and connection["type"] in {"AzureOpenAIConnection", "OpenAIConnection"}) or \
       isinstance(connection, (AzureOpenAIConnection, OpenAIConnection)):
        return [
            {"value": "chat", "display_value": "chat"},
            {"value": "completion", "display_value": "completion"},
        ]
    else:
        return [
            {"value": "chat", "display_value": "chat"},
        ]


# need to set metadata "streaming_option_parameter" to support serving streaming functionality.
@tool(streaming_option_parameter="stream")
@handle_openai_error()
def llm(
    # connection can be of type AzureOpenAIConnection, OpenAIConnection, ServerlessConnection.
    # ServerlessConnection was introduced in pf version 1.6.0.
    # cannot set type hint here to be compatible with pf version < 1.6.0.
    connection,
    prompt: PromptTemplate,
    api: str = "chat",
    deployment_name: str = "", model: str = "",
    temperature: float = 1.0,
    top_p: float = 1.0,
    # stream is a hidden to the end user, it is only supposed to be set by the executor.
    stream: bool = False,
    stop: list = None,
    max_tokens: int = None,
    presence_penalty: float = 0,
    frequency_penalty: float = 0,
    logit_bias: dict = {},
    # tool_choice can be of type str or dict.
    tool_choice: object = None,
    tools: list = None,
    response_format: object = None,
    seed: int = None,
    suffix: str = None,
    logprobs: int = None,
    echo: bool = False,
    best_of: int = 1,
    **kwargs,
):
    # TODO: get rid of `register_apis` dependency from llm.py.
    if isinstance(connection, AzureOpenAIConnection):
        if api == "completion":
            return AzureOpenAI(connection).completion(
                prompt=prompt,
                deployment_name=deployment_name,
                temperature=temperature,
                top_p=top_p,
                stream=stream,
                stop=stop,
                max_tokens=max_tokens,
                presence_penalty=presence_penalty,
                frequency_penalty=frequency_penalty,
                logit_bias=logit_bias,
                suffix=suffix,
                logprobs=logprobs,
                echo=echo,
                best_of=best_of,
                **kwargs
            )
        else:
            return AzureOpenAI(connection).chat(
                prompt=prompt,
                deployment_name=deployment_name,
                temperature=temperature,
                top_p=top_p,
                stream=stream,
                stop=stop,
                max_tokens=max_tokens,
                presence_penalty=presence_penalty,
                frequency_penalty=frequency_penalty,
                logit_bias=logit_bias,
                tool_choice=tool_choice,
                tools=tools,
                response_format=response_format,
                seed=seed,
                **kwargs
            )
    elif isinstance(connection, (OpenAIConnection, ServerlessConnection)):
        if api == "completion":
            return OpenAI(connection).completion(
                prompt=prompt,
                model=model,
                temperature=temperature,
                top_p=top_p,
                stream=stream,
                stop=stop,
                max_tokens=max_tokens,
                presence_penalty=presence_penalty,
                frequency_penalty=frequency_penalty,
                logit_bias=logit_bias,
                suffix=suffix,
                logprobs=logprobs,
                echo=echo,
                best_of=best_of,
                **kwargs
            )
        else:
            return OpenAI(connection).chat(
                prompt=prompt,
                model=model,
                temperature=temperature,
                top_p=top_p,
                stream=stream,
                stop=stop,
                max_tokens=max_tokens,
                presence_penalty=presence_penalty,
                frequency_penalty=frequency_penalty,
                logit_bias=logit_bias,
                tool_choice=tool_choice,
                tools=tools,
                response_format=response_format,
                seed=seed,
                **kwargs
            )
    else:
        error_message = f"Not Support connection type '{type(connection).__name__}' for llm. " \
                        "Connection type should be in [AzureOpenAIConnection, OpenAIConnection" \
                        ", ServerlessConnection]."
        raise InvalidConnectionType(message=error_message)
