from promptflow.tools.common import handle_openai_error
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
    deployment_name: str = "",
    model: str = "",
    temperature: float = 1.0,
    top_p: float = 1.0,
    # stream is a hidden to the end user, it is only supposed to be set by the executor.
    stream: bool = False,
    stop: list = None,
    max_tokens: int = None,
    presence_penalty: float = None,
    frequency_penalty: float = None,
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
