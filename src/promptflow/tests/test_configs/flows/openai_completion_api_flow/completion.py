from openai.version import VERSION as OPENAI_VERSION
import openai

from promptflow import tool
from promptflow.connections import AzureOpenAIConnection

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
def completion(connection: AzureOpenAIConnection, prompt: str) -> str:
    stream = True
    if OPENAI_VERSION.startswith("0."):
        completion = openai.Completion.create(
            prompt=prompt,
            engine="text-davinci-003",
            max_tokens=256,
            temperature=0.8,
            top_p=1.0,
            n=1,
            stream=stream,
            stop=None,
            **dict(connection),
        )
    else:
        completion = get_client(connection).completions.create(
            prompt=prompt,
            model="text-davinci-003",
            max_tokens=256,
            temperature=0.8,
            top_p=1.0,
            n=1,
            stream=stream,
            stop=None,
            **dict(connection),
        )

    if stream:
        def generator():
            for chunk in completion:
                if chunk.choices:
                    yield getattr(chunk.choices[0], "text", "")

        return "".join(generator())
    else:
        return getattr(completion.choices[0], "text", "")
