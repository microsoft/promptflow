from openai.version import VERSION as OPENAI_VERSION
import openai

from promptflow.core import tool
from promptflow.connections import AzureOpenAIConnection

IS_LEGACY_OPENAI = OPENAI_VERSION.startswith("0.")


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
def completion(connection: AzureOpenAIConnection, prompt: str, stream: bool) -> str:
    if IS_LEGACY_OPENAI:
        completion = openai.Completion.create(
            prompt=prompt,
            engine="gpt-35-turbo-instruct",
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
            model="gpt-35-turbo-instruct",
            max_tokens=256,
            temperature=0.8,
            top_p=1.0,
            n=1,
            stream=stream,
            stop=None,
        )

    if stream:
        def generator():
            for chunk in completion:
                if chunk.choices:
                    if IS_LEGACY_OPENAI:
                        yield getattr(chunk.choices[0], "text", "")
                    else:
                        yield chunk.choices[0].text or ""

        return generator()
    else:
        if IS_LEGACY_OPENAI:
            return getattr(completion.choices[0], "text", "")
        else:
            return completion.choices[0].text or ""
