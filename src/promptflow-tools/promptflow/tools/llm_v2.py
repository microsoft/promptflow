from typing import Union

from openai import AzureOpenAI as AzureOpenAIClient, OpenAI as OpenAIClient
from promptflow.tools.common import render_jinja_template, handle_openai_error, parse_chat, \
    preprocess_template_string, find_referenced_image_set, convert_to_chat_list, normalize_connection_config, \
    post_process_chat_api_response, validate_functions, process_function_call
from promptflow.tools.exception import InvalidConnectionType
from promptflow.contracts.types import PromptTemplate

# Avoid circular dependencies: Use import 'from promptflow._internal' instead of 'from promptflow'
# since the code here is in promptflow namespace as well
from promptflow._internal import tool
from promptflow.connections import AzureOpenAIConnection, OpenAIConnection, ServerlessConnection


@tool
@handle_openai_error()
def llm(
    connection: Union[AzureOpenAIConnection, OpenAIConnection, ServerlessConnection], 
    prompt: PromptTemplate,
    api_of_aoai: str = "chat",
    api_of_oai: str = "chat",
    api_of_serverless: str = "chat",
    deployment_name_of_chat: str = "",
    deployment_name_of_completion: str = "",
    model_of_chat: str = "",
    model_of_completion: str = "",
    temperature: float = 1.0,
    top_p: float = 1.0,
    # stream is a hidden to the end user, it is only supposed to be set by the executor.
    stream: bool = False,
    stop: list = None,
    max_tokens: int = None,
    presence_penalty: float = 0,
    frequency_penalty: float = 0,
    logit_bias: dict = {},
    # function_call can be of type str or dict.
    function_call: object = None,
    functions: list = None,
    response_format: object = None,
    **kwargs,
):
    # 1. init client
    # api = ""
    if isinstance(connection, AzureOpenAIConnection):
        client = AzureOpenAIClient(**normalize_connection_config(connection))
        api = api_of_aoai
    elif isinstance(connection, (OpenAIConnection, ServerlessConnection)):
        client = OpenAIClient(**normalize_connection_config(connection))
        api = api_of_oai if isinstance(connection, OpenAIConnection) else api_of_serverless
    else:
        error_message = f"Not Support connection type '{type(connection).__name__}' for embedding api. " \
                        f"Connection type should be in [AzureOpenAIConnection, OpenAIConnection]."
        raise InvalidConnectionType(message=error_message)

    # 3. prepare params
    params = {
        "temperature": temperature,
        "top_p": top_p,
        "n": 1,
        "stream": stream,
        "presence_penalty": presence_penalty,
        "frequency_penalty": frequency_penalty,
    }

    # deal with prompt
    # keep_trailing_newline=True is to keep the last \n in the prompt to avoid converting "user:\t\n" to "user:".
    prompt = preprocess_template_string(prompt)
    referenced_images = find_referenced_image_set(kwargs)

    # convert list type into ChatInputList type
    converted_kwargs = convert_to_chat_list(kwargs)
    rendered_prompt = render_jinja_template(prompt, trim_blocks=True, keep_trailing_newline=True, **converted_kwargs)
    if api == "completion":
        params["prompt"] = rendered_prompt
    else:
        params["messages"] = parse_chat(rendered_prompt, list(referenced_images))

    # to avoid gptv model validation error for empty param values.
    if stop:
        params["stop"] = stop
    if max_tokens is not None:
        params["max_tokens"] = max_tokens
    if logit_bias:
        params["logit_bias"] = logit_bias
    if response_format:
        params["response_format"] = response_format

    if functions is not None:
        validate_functions(functions)
        params["functions"] = functions
        params["function_call"] = process_function_call(function_call)

    if isinstance(connection, AzureOpenAIConnection):
        params["model"] = deployment_name_of_completion if api == "completion" else deployment_name_of_chat
        params["extra_headers"] = {"ms-azure-ai-promptflow-called-from": "aoai-tool"}
    elif isinstance(connection, OpenAIConnection):
        params["model"] = model_of_completion if api == "completion" else model_of_chat

    # 4. call api
    if api == "completion":
        return client.completions.create(**params).choices[0].text
    else:
        completion = client.chat.completions.create(**params)
        return post_process_chat_api_response(completion, stream, None)
