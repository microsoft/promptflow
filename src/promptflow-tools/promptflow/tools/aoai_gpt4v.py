try:
    from openai import AzureOpenAI as AzureOpenAIClient
except Exception:
    raise Exception(
        "Please upgrade your OpenAI package to version 1.0.0 or later using the command: pip install --upgrade openai.")

from promptflow._internal import ToolProvider, tool
from promptflow.connections import AzureOpenAIConnection
from promptflow.contracts.types import PromptTemplate
from promptflow._core.openai_injector import inject

from promptflow.tools.common import render_jinja_template, handle_openai_error, parse_chat, \
    preprocess_template_string, find_referenced_image_set, convert_to_chat_list, normalize_connection_config, \
    post_process_chat_api_response


KEY_BASED_AOAI_TYPE = "azure"
TOKEN_BASED_AOAI_TYPE = "azure_ad"

def chat_completion(*args, **kwargs):
    azure_endpoint = kwargs.pop("azure_endpoint", None)
    api_version = kwargs.pop("api_version", None)
    api_type = kwargs.pop("api_type", None)

    if api_type == KEY_BASED_AOAI_TYPE:
        api_key = kwargs.pop("api_key", None)
        client = AzureOpenAIClient(azure_endpoint=azure_endpoint, api_version=api_version, api_key=api_key)
    elif api_type == TOKEN_BASED_AOAI_TYPE:
        client = AzureOpenAIClient(azure_endpoint=azure_endpoint, api_version=api_version)

    deployment_name = kwargs.pop("deployment_name", None)

    extra_headers = kwargs.pop("headers", None)
    temperature = kwargs.pop("temperature", None)
    top_p = kwargs.pop("top_p", None)
    n = kwargs.pop("n", None)
    stream = kwargs.pop("stream", None)
    stop = kwargs.pop("stop", None)
    max_tokens = kwargs.pop("max_tokens", None)
    presence_penalty = kwargs.pop("presence_penalty", None)
    frequency_penalty = kwargs.pop("frequency_penalty", None)
    messages = kwargs.pop("messages", None)

    data = {
        "messages": messages,
        "temperature": temperature,
        "top_p": top_p,
        "n": n,
        "stream": stream,
        "presence_penalty": presence_penalty,
        "frequency_penalty": frequency_penalty,
        "extra_headers": extra_headers
    }

    if stop:
        data["stop"] = stop
    if max_tokens and str(max_tokens).lower() != "inf":
        data["max_tokens"] = int(max_tokens)

    return client.chat.completions.create(model=deployment_name, **data)


if not hasattr(chat_completion, "_original"):
    chat_completion = inject(chat_completion)


class AzureOpenAI(ToolProvider):
    def __init__(self, connection: AzureOpenAIConnection):
        super().__init__()
        self.connection = connection
        self._connection_dict = normalize_connection_config(self.connection)

    @tool(streaming_option_parameter="stream")
    @handle_openai_error()
    def chat(
        self,
        prompt: PromptTemplate,
        deployment_name: str,
        temperature: float = 1.0,
        top_p: float = 1.0,
        # stream is a hidden to the end user, it is only supposed to be set by the executor.
        stream: bool = False,
        stop: list = None,
        max_tokens: int = None,
        presence_penalty: float = 0,
        frequency_penalty: float = 0,
        **kwargs,
    ) -> str:
        # keep_trailing_newline=True is to keep the last \n in the prompt to avoid converting "user:\t\n" to "user:".
        prompt = preprocess_template_string(prompt)
        referenced_images = find_referenced_image_set(kwargs)

        # convert list type into ChatInputList type
        converted_kwargs = convert_to_chat_list(kwargs)
        chat_str = render_jinja_template(prompt, trim_blocks=True, keep_trailing_newline=True, **converted_kwargs)
        messages = parse_chat(chat_str, list(referenced_images))

        azure_endpoint = self._connection_dict.get("azure_endpoint")
        api_version = self._connection_dict.get("api_version")
        api_key = self._connection_dict.get("api_key")
        api_type = self._connection_dict.get("api_type")

        headers = {
            "Content-Type": "application/json",
            "ms-azure-ai-promptflow-called-from": "aoai-gpt4v-tool"
        }

        completion = chat_completion(
            azure_endpoint=azure_endpoint,
            api_version=api_version,
            api_type=api_type,
            api_key=api_key,
            deployment_name=deployment_name,
            headers=headers,
            stream=stream,
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            stop=stop,
            max_tokens=max_tokens,
            presence_penalty=presence_penalty,
            frequency_penalty=frequency_penalty)

        return post_process_chat_api_response(completion, stream, None)
