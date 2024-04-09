from typing import Union

from promptflow.tools.common import handle_openai_error
from promptflow.tools.exception import InvalidConnectionType
from promptflow.contracts.types import PromptTemplate

# Avoid circular dependencies: Use import 'from promptflow._internal' instead of 'from promptflow'
# since the code here is in promptflow namespace as well
from promptflow._internal import tool
from promptflow.connections import AzureOpenAIConnection, OpenAIConnection
from promptflow.tools.aoai_gpt4v import AzureOpenAI
from promptflow.tools.openai_gpt4v import OpenAI


# need to set metadata "streaming_option_parameter" to support serving streaming functionality.
@tool(streaming_option_parameter="stream")
@handle_openai_error()
def llm_vision(
    connection: Union[AzureOpenAIConnection, OpenAIConnection],
    prompt: PromptTemplate,
    deployment_name: str = "", model: str = "",
    temperature: float = 1.0,
    top_p: float = 1.0,
    # stream is a hidden to the end user, it is only supposed to be set by the executor.
    stream: bool = False,
    stop: list = None,
    max_tokens: int = None,
    presence_penalty: float = 0,
    frequency_penalty: float = 0,
    seed: int = None,
    detail: str = 'auto',
    **kwargs,
):
    if isinstance(connection, AzureOpenAIConnection):
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
            seed=seed,
            detail=detail,
            **kwargs
        )
    elif isinstance(connection, OpenAIConnection):
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
            seed=seed,
            detail=detail,
            **kwargs
        )
    else:
        error_message = f"Not Support connection type '{type(connection).__name__}' for llm. " \
                        "Connection type should be in [AzureOpenAIConnection, OpenAIConnection]."
        raise InvalidConnectionType(message=error_message)
