import random
import time

from promptflow.core import tool
from promptflow.connections import AzureOpenAIConnection
from promptflow.tools.common import parse_chat


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


@tool
def say_thanks(
    name: str,
    connection: AzureOpenAIConnection = None,
    **kwargs,
) -> str:
    """Generate thanks statement

    :param name: The name to be say thanks to.
    :type name: str
    :param connection: The connection to Azure OpenAI.
    :type connection: AzureOpenAIConnection
    """
    prompt = f"""
            system:
              You task is to generate what I ask
            user:
              Please repeat below:
              'Thanks for your help, {name}!'
            """
    print(f"Say thanks with prompt: {prompt}")
    deployment_name="gpt-35-turbo"
    max_tokens=120
    temperature = 1.0
    top_p = 1.0
    n= 1
    stop = None
    presence_penalty = 0
    frequency_penalty = 0

    logit_bias= {}
    user =  ""
    messages = parse_chat(prompt)
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
