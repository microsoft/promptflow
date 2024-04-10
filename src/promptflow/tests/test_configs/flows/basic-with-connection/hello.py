import json
import os
import openai
from openai.version import VERSION as OPENAI_VERSION

from promptflow.core import tool
from promptflow.connections import AzureOpenAIConnection
from promptflow.tools.common import render_jinja_template, parse_chat


# The inputs section will change based on the arguments of the tool function, after you save the code
# Adding type to arguments and return value will help the system show the types properly
# Please update the function name/signature per need

def get_client(connection: AzureOpenAIConnection):
    api_key = connection.api_key
    conn = dict(
        api_key=connection.api_key,
    )
    if api_key.startswith("sk-"):
        from openai import OpenAI as Client
    else:
        from openai import AzureOpenAI as Client
        conn.update(
            azure_endpoint=connection.api_base,
            api_version=connection.api_version,
        )
    return Client(**conn)

def to_bool(value) -> bool:
    return str(value).lower() == "true"


@tool
def my_python_tool(
    prompt: str,
    # for AOAI, deployment name is customized by user, not model name.
    deployment_name: str,
    suffix: str = None,
    max_tokens: int = 120,
    temperature: float = 1.0,
    top_p: float = 1.0,
    n: int = 1,
    logprobs: int = None,
    echo: bool = False,
    stop: list = None,
    presence_penalty: float = 0,
    frequency_penalty: float = 0,
    best_of: int = 1,
    logit_bias: dict = {},
    user: str = "",
    connection: AzureOpenAIConnection = None,
    **kwargs,
) -> str:

    # TODO: remove below type conversion after client can pass json rather than string.
    echo = to_bool(echo)
    # Assert environment variable resolved
    assert os.environ["API_TYPE"] == connection.api_type
    if OPENAI_VERSION.startswith("0."):
        response = openai.Completion.create(
            prompt=prompt,
            engine=deployment_name,
            # empty string suffix should be treated as None.
            suffix=suffix if suffix else None,
            max_tokens=int(max_tokens),
            temperature=float(temperature),
            top_p=float(top_p),
            n=int(n),
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
            request_timeout=30,
            **dict(connection),
        )
        return response.choices[0].text
    else:
        chat_str = render_jinja_template(prompt, trim_blocks=True, keep_trailing_newline=True, **kwargs)
        messages = parse_chat(chat_str)
        response = get_client(connection).chat.completions.create(
            messages=messages,
            model=deployment_name,
            max_tokens=int(max_tokens),
            temperature=float(temperature),
            top_p=float(top_p),
            n=int(n),
            # fix bug "[] is not valid under any of the given schemas-'stop'"
            stop=stop if stop else None,
            presence_penalty=float(presence_penalty),
            frequency_penalty=float(frequency_penalty),
            # Logit bias must be a dict if we passed it to openai api.
            logit_bias=logit_bias if logit_bias else {},
            user=user
        )
        return response.choices[0].message.content
