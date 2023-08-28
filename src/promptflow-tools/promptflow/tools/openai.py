from dataclasses import asdict
from enum import Enum

import openai

from promptflow.connections import OpenAIConnection
from promptflow.contracts.types import PromptTemplate
from promptflow._internal import ToolProvider, tool, register_apis
from promptflow.tools.common import render_jinja_template, handle_openai_error, \
    parse_chat, to_bool, validate_functions, process_function_call, post_process_chat_api_response


class Engine(str, Enum):
    TEXT_DAVINCI_001 = "text-davinci-001"
    TEXT_DAVINCI_002 = "text-davinci-002"
    TEXT_DAVINCI_003 = "text-davinci-003"
    TEXT_CURIE_001 = "text-curie-001"
    TEXT_BABBAGE_001 = "text-babbage-001"
    TEXT_ADA_001 = "text-ada-001"
    CODE_CUSHMAN_001 = "code-cushman-001"
    CODE_DAVINCI_002 = "code-davinci-002"


class OpenAI(ToolProvider):
    def __init__(self, connection: OpenAIConnection):
        super().__init__()
        self.connection = connection
        self._connection_dict = asdict(self.connection)

    @tool
    @handle_openai_error()
    def completion(
            self,
            prompt: PromptTemplate,
            model: Engine = Engine.TEXT_DAVINCI_003,
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
        response = openai.Completion.create(
            prompt=prompt,
            model=model.value if isinstance(model, Enum) else model,
            # empty string suffix should be treated as None.
            suffix=suffix if suffix else None,
            max_tokens=int(max_tokens),
            temperature=float(temperature),
            top_p=float(top_p),
            n=int(n),
            stream=stream,
            logprobs=int(logprobs) if logprobs else None,
            echo=echo,
            stop=stop if stop else None,
            presence_penalty=float(presence_penalty),
            frequency_penalty=float(frequency_penalty),
            best_of=int(best_of),
            # Logit bias must be a dict if we passed it to openai api.
            logit_bias=logit_bias if logit_bias else {},
            user=user,
            **self._connection_dict,
        )

        if stream:
            def generator():
                for chunk in response:
                    if chunk.choices:
                        yield getattr(chunk.choices[0], "text", "")

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
            model: str = "gpt-3.5-turbo",
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
            function_call: str = None,
            functions: list = None,
            **kwargs,
    ) -> [str, dict]:
        chat_str = render_jinja_template(prompt, trim_blocks=True, keep_trailing_newline=True, **kwargs)
        messages = parse_chat(chat_str)
        # TODO: remove below type conversion after client can pass json rather than string.
        stream = to_bool(stream)
        params = {
            "model": model,
            "messages": messages,
            "temperature": float(temperature),
            "top_p": float(top_p),
            "n": int(n),
            "stream": stream,
            "stop": stop if stop else None,
            "max_tokens": int(max_tokens) if max_tokens and str(max_tokens).lower() != "inf" else None,
            "presence_penalty": float(presence_penalty),
            "frequency_penalty": float(frequency_penalty),
            "logit_bias": logit_bias,
            "user": user
        }

        if functions is not None:
            validate_functions(functions)
            params["functions"] = functions
            params["function_call"] = process_function_call(function_call)

        completion = openai.ChatCompletion.create(**{**self._connection_dict, **params})
        return post_process_chat_api_response(completion, stream, functions)

    # TODO: embedding is a separate builtin tool, will remove it from llm.
    @tool
    @handle_openai_error()
    def embedding(self, input, model: str = "text-embedding-ada-002", user: str = ""):
        response = openai.Embedding.create(
            input=input,
            model=model,
            user=user,
            **self._connection_dict,
        )
        return response["data"][0]["embedding"]


register_apis(OpenAI)


@tool
def completion(
        connection: OpenAIConnection,
        prompt: PromptTemplate,
        model: Engine = Engine.TEXT_DAVINCI_003,
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
) -> [str, dict]:
    return OpenAI(connection).completion(
        prompt=prompt,
        model=model,
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
        connection: OpenAIConnection,
        prompt: PromptTemplate,
        model: str = "gpt-3.5-turbo",
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
        function_call: str = None,
        functions: list = None,
        **kwargs,
) -> [str, dict]:
    return OpenAI(connection).chat(
        prompt=prompt,
        model=model,
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
        **kwargs,
    )
