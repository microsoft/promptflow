from promptflow.connections import OpenAIConnection
from promptflow.contracts.types import PromptTemplate
from promptflow._internal import ToolProvider, tool
from promptflow.tools.common import handle_openai_error, build_messages, \
    post_process_chat_api_response, preprocess_template_string, \
    find_referenced_image_set, convert_to_chat_list, init_openai_client


class OpenAI(ToolProvider):
    def __init__(self, connection: OpenAIConnection):
        super().__init__()
        self._client = init_openai_client(connection)

    @tool(streaming_option_parameter="stream")
    @handle_openai_error()
    def chat(
        self,
        prompt: PromptTemplate,
        model: str = "gpt-4-vision-preview",
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
    ) -> [str, dict]:
        prompt = preprocess_template_string(prompt)
        referenced_images = find_referenced_image_set(kwargs)

        # convert list type into ChatInputList type
        converted_kwargs = convert_to_chat_list(kwargs)
        messages = build_messages(prompt=prompt, images=list(referenced_images), detail=detail, **converted_kwargs)

        params = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "n": 1,
            "stream": stream,
            "presence_penalty": presence_penalty,
            "frequency_penalty": frequency_penalty,
        }

        if stop:
            params["stop"] = stop
        if max_tokens is not None:
            params["max_tokens"] = max_tokens
        if seed is not None:
            params["seed"] = seed

        completion = self._client.chat.completions.create(**params)
        return post_process_chat_api_response(completion, stream)
