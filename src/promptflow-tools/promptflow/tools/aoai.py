import json
from promptflow.tools.common import render_jinja_template, handle_openai_error, parse_chat, to_bool, \
    validate_functions, process_function_call, post_process_chat_api_response, init_azure_openai_client

# Avoid circular dependencies: Use import 'from promptflow._internal' instead of 'from promptflow'
# since the code here is in promptflow namespace as well
from promptflow._internal import enable_cache, ToolProvider, tool, register_apis
from promptflow.connections import AzureOpenAIConnection
from promptflow.contracts.types import PromptTemplate


class AzureOpenAI(ToolProvider):
    def __init__(self, connection: AzureOpenAIConnection):
        super().__init__()
        self.connection = connection
        self._client = init_azure_openai_client(connection)

    def calculate_cache_string_for_completion(
        self,
        **kwargs,
    ) -> str:
        d = dict(self.connection)
        d.pop("api_key")
        d.update({**kwargs})
        return json.dumps(d)

    @tool
    @handle_openai_error()
    @enable_cache(calculate_cache_string_for_completion)
    def completion(
        self,
        prompt: PromptTemplate,
        # for AOAI, deployment name is customized by user, not model name.
        deployment_name: str,
        suffix: str = None,
        max_tokens: int = 16,
        temperature: float = 1.0,
        top_p: float = 1.0,
        n: int = 1,
        # stream is a hidden to the end user, it is only supposed to be set by the executor.
        stream: bool = False,
        logprobs: int = None,
        echo: bool = False,
        stop: list = None,
        presence_penalty: float = 0,
        frequency_penalty: float = 0,
        best_of: int = 1,
        logit_bias: dict = {},
        user: str = "",
        **kwargs,
    ) -> str:
        prompt = render_jinja_template(prompt, trim_blocks=True, keep_trailing_newline=True, **kwargs)
        # TODO: remove below type conversion after client can pass json rather than string.
        echo = to_bool(echo)
        stream = to_bool(stream)
        response = self._client.completions.create(
            prompt=prompt,
            model=deployment_name,
            # empty string suffix should be treated as None.
            suffix=suffix if suffix else None,
            max_tokens=int(max_tokens),
            temperature=float(temperature),
            top_p=float(top_p),
            n=int(n),
            stream=stream,
            # TODO: remove below type conversion after client pass json rather than string.
            # empty string will go to else branch, but original api cannot accept empty
            # string, must be None.
            logprobs=int(logprobs) if logprobs else None,
            echo=echo,
            # fix bug "[] is not valid under any of the given schemas-'stop'"
            stop=stop if stop else None,
            presence_penalty=float(presence_penalty),
            frequency_penalty=float(frequency_penalty),
            best_of=int(best_of),
            # Logit bias must be a dict if we passed it to openai api.
            logit_bias=logit_bias if logit_bias else {},
            user=user,
            extra_headers={"ms-azure-ai-promptflow-called-from": "aoai-tool"})

        if stream:
            def generator():
                for chunk in response:
                    if chunk.choices:
                        yield chunk.choices[0].text if hasattr(chunk.choices[0], 'text') and \
                               chunk.choices[0].text is not None else ""

            # We must return the generator object, not using yield directly here.
            # Otherwise, the function itself will become a generator, despite whether stream is True or False.
            return generator()
        else:
            # get first element because prompt is single.
            return response.choices[0].text

    @tool
    @handle_openai_error()
    def chat(
        self,
        prompt: PromptTemplate,
        # for AOAI, deployment name is customized by user, not model name.
        deployment_name: str,
        temperature: float = 1.0,
        top_p: float = 1.0,
        n: int = 1,
        # stream is a hidden to the end user, it is only supposed to be set by the executor.
        stream: bool = False,
        stop: list = None,
        max_tokens: int = None,
        presence_penalty: float = 0,
        frequency_penalty: float = 0,
        logit_bias: dict = {},
        user: str = "",
        # function_call can be of type str or dict.
        function_call: object = None,
        functions: list = None,
        response_format: object = None,
        seed: int = None,
        **kwargs,
    ) -> [str, dict]:
        # keep_trailing_newline=True is to keep the last \n in the prompt to avoid converting "user:\t\n" to "user:".
        chat_str = render_jinja_template(prompt, trim_blocks=True, keep_trailing_newline=True, **kwargs)
        messages = parse_chat(chat_str)
        # TODO: remove below type conversion after client can pass json rather than string.
        stream = to_bool(stream)
        params = {
            "model": deployment_name,
            "messages": messages,
            "temperature": float(temperature),
            "top_p": float(top_p),
            "n": int(n),
            "stream": stream,
            "presence_penalty": float(presence_penalty),
            "frequency_penalty": float(frequency_penalty),
            "user": user,
            "extra_headers": {"ms-azure-ai-promptflow-called-from": "aoai-tool"}
        }
        if functions is not None:
            validate_functions(functions)
            params["functions"] = functions
            params["function_call"] = process_function_call(function_call)

        # to avoid vision model validation error for empty param values.
        if stop:
            params["stop"] = stop
        if max_tokens is not None and str(max_tokens).lower() != "inf":
            params["max_tokens"] = int(max_tokens)
        if logit_bias:
            params["logit_bias"] = logit_bias
        if response_format:
            params["response_format"] = response_format
        if seed is not None:
            params["seed"] = seed

        completion = self._client.chat.completions.create(**params)
        return post_process_chat_api_response(completion, stream, functions)


register_apis(AzureOpenAI)


@tool
def completion(
    connection: AzureOpenAIConnection,
    prompt: PromptTemplate,
    deployment_name: str,
    suffix: str = None,
    max_tokens: int = 16,
    temperature: float = 1.0,
    top_p: float = 1,
    n: int = 1,
    stream: bool = False,
    logprobs: int = None,
    echo: bool = False,
    stop: list = None,
    presence_penalty: float = 0,
    frequency_penalty: float = 0,
    best_of: int = 1,
    logit_bias: dict = {},
    user: str = "",
    **kwargs,
) -> str:
    return AzureOpenAI(connection).completion(
        prompt=prompt,
        deployment_name=deployment_name,
        suffix=suffix,
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
        n=n,
        stream=stream,
        logprobs=logprobs,
        echo=echo,
        stop=stop if stop else None,
        presence_penalty=presence_penalty,
        frequency_penalty=frequency_penalty,
        best_of=best_of,
        logit_bias=logit_bias,
        user=user,
        **kwargs,
    )


@tool
def chat(
    connection: AzureOpenAIConnection,
    prompt: PromptTemplate,
    deployment_name: str,
    temperature: float = 1,
    top_p: float = 1,
    n: int = 1,
    stream: bool = False,
    stop: list = None,
    max_tokens: int = None,
    presence_penalty: float = 0,
    frequency_penalty: float = 0,
    logit_bias: dict = {},
    user: str = "",
    function_call: object = None,
    functions: list = None,
    response_format: object = None,
    seed: int = None,
    **kwargs,
) -> str:
    # chat model is not available in azure openai, so need to set the environment variable.
    return AzureOpenAI(connection).chat(
        prompt=prompt,
        deployment_name=deployment_name,
        temperature=temperature,
        top_p=top_p,
        n=n,
        stream=stream,
        stop=stop if stop else None,
        max_tokens=max_tokens,
        presence_penalty=presence_penalty,
        frequency_penalty=frequency_penalty,
        logit_bias=logit_bias,
        user=user,
        function_call=function_call,
        functions=functions,
        response_format=response_format,
        seed=seed,
        **kwargs,
    )
