import openai

from promptflow.contracts.types import PromptTemplate
from promptflow._internal import tool
from promptflow.tools.common import render_jinja_template, handle_openai_error, \
    parse_chat, to_bool, post_process_chat_api_response, preprocess_template_string, \
    find_referenced_image_set, convert_to_chat_list


@tool
@handle_openai_error()
def chat(
        prompt: PromptTemplate,
        model: str = "gpt-4-vision-preview",
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
) -> [str, dict]:
    _connection_dict = dict(kwargs.pop("connection", {}))

    # keep_trailing_newline=True is to keep the last \n in the prompt to avoid converting "user:\t\n" to "user:".
    prompt = preprocess_template_string(prompt)
    referenced_images = find_referenced_image_set(kwargs)

    # convert list type into ChatInputList type
    converted_kwargs = convert_to_chat_list(kwargs)
    chat_str = render_jinja_template(prompt, trim_blocks=True, keep_trailing_newline=True, **converted_kwargs)
    messages = parse_chat(chat_str, list(referenced_images))

    # TODO: remove below type conversion after client can pass json rather than string.
    stream = to_bool(stream)
    params = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "top_p": top_p,
        "n": n,
        "stream": stream,
        "presence_penalty": presence_penalty,
        "frequency_penalty": frequency_penalty,
    }

    if stop:
        params["stop"] = stop
    if max_tokens:
        params["max_tokens"] = max_tokens

    completion = openai.ChatCompletion.create(**{**_connection_dict, **params})
    return post_process_chat_api_response(completion, stream, None)
