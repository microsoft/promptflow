import re
import requests

from openai import error

from promptflow._internal import ToolProvider, tool
from promptflow.connections import AzureOpenAIConnection
from promptflow.contracts.types import PromptTemplate
from promptflow._core.openai_injector import inject

from promptflow.tools.common import render_jinja_template, handle_openai_error, parse_chat, \
    preprocess_template_string, find_referenced_image_set, convert_to_chat_list


KEY_BASED_AOAI_TYPE = "azure"
TOKEN_BASED_AOAI_TYPE = "azure_ad"
VALID_ROLES = {"system", "user", "assistant"}


def preprocess_template_string(template_string: str) -> str:
    """Remove the image input decorator from the template string and place the image input in a new line."""
    pattern = re.compile(r'\!\[(\s*image\s*)\]\(\{\{(\s*[\S^{}]+\s*)\}\}\)')

    # Find all matches in the input string
    matches = pattern.findall(template_string)

    # Perform substitutions
    for match in matches:
        original = f"![{match[0]}]({{{{{match[1]}}}}})"
        replacement = f"\n{{{{{match[1]}}}}}\n"
        template_string = template_string.replace(original, replacement)

    return template_string


def get_gpt4v_response(end_point: str, headers: dict, data: dict) -> requests.Response:
    """Call GPT-4V API and return the response."""
    try:
        response = requests.post(end_point, headers=headers, json=data)
    except requests.exceptions.Timeout as e:
        raise error.Timeout("Request timed out: {}".format(e)) from e
    except requests.exceptions.RequestException as e:
        raise error.APIConnectionError("Error communicating with OpenAI: {}".format(e)) from e

    status_code = response.status_code
    if status_code == 401 or status_code == 403:
        raise error.PermissionError(message=response.text)
    elif status_code == 429:
        raise error.RateLimitError(message=response.text)
    elif status_code >= 500:
        raise error.ServiceUnavailableError(message=response.text)
    elif status_code >= 400:
        raise error.InvalidRequestError(message=response.text, param=data)

    return response.json()


def chat_completion(*args, **kwargs):
    api_base = kwargs.pop("api_base", None)
    api_version = kwargs.pop("api_version", None)
    deployment_name = kwargs.pop("deployment_name", None)
    gpt4v_endpoint = f"{api_base}/openai/deployments/{deployment_name}/chat/completions?api-version={api_version}"

    headers = kwargs.pop("headers", None)
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
        "frequency_penalty": frequency_penalty
    }

    if stop:
        data["stop"] = stop
    if max_tokens and str(max_tokens).lower() != "inf":
        data["max_tokens"] = int(max_tokens)
    return get_gpt4v_response(gpt4v_endpoint, headers=headers, data=data)


if not hasattr(chat_completion, "_original"):
    chat_completion = inject(chat_completion)


class GPT4v(ToolProvider):
    def __init__(self, connection: AzureOpenAIConnection):
        super().__init__()
        self.connection = connection
        self._connection_dict = dict(self.connection)

    @tool(streaming_option_parameter="stream")
    @handle_openai_error()
    def chat(
        self,
        prompt: PromptTemplate,
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
        **kwargs,
    ) -> str:
        # keep_trailing_newline=True is to keep the last \n in the prompt to avoid converting "user:\t\n" to "user:".
        prompt = preprocess_template_string(prompt)
        referenced_images = find_referenced_image_set(kwargs)

        # convert list type into ChatInputList type
        converted_kwargs = convert_to_chat_list(kwargs)
        chat_str = render_jinja_template(prompt, trim_blocks=True, keep_trailing_newline=True, **converted_kwargs)
        messages = parse_chat(chat_str, list(referenced_images))

        api_base = self._connection_dict.get("api_base")
        api_version = self._connection_dict.get("api_version")
        api_key = self._connection_dict.get("api_key")
        api_type = self._connection_dict.get("api_type")

        headers = {
            "Content-Type": "application/json",
            "ms-azure-ai-promptflow-called-from": "aoai-gpt4v-tool"
        }

        if api_type == KEY_BASED_AOAI_TYPE:
            headers["api-key"] = api_key
        elif api_type == TOKEN_BASED_AOAI_TYPE:
            token = self.connection.get_token()
            headers["Authorization"] = f"Bearer {token}"

        completion = chat_completion(
            api_base=api_base,
            api_version=api_version,
            api_type=api_type,
            deployment_name=deployment_name,
            headers=headers,
            stream=stream,
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            n=n,
            stop=stop,
            max_tokens=max_tokens,
            presence_penalty=presence_penalty,
            frequency_penalty=frequency_penalty)

        if "choices" not in completion or len(completion["choices"]) == 0 or "message" not in completion["choices"][0] or "content" not in completion["choices"][0]["message"]:
            raise error.APIError(message="Invalid response from Azure OpenAI GPT-4V: {}".format(completion))

        return completion['choices'][0]['message']['content']
