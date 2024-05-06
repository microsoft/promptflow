import openai
from openai.version import VERSION as OPENAI_VERSION
from typing import List

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


def create_messages(question, chat_history):
    yield {"role": "system", "content": "You are a helpful assistant."}
    for chat in chat_history:
        yield {"role": "user", "content": chat["inputs"]["question"]}
        yield {"role": "assistant", "content": chat["outputs"]["answer"]}
        yield {"role": "user", "content": question}


@tool
def chat(connection: AzureOpenAIConnection, question: str, chat_history: List, stream: bool) -> str:
    if IS_LEGACY_OPENAI:
        completion = openai.ChatCompletion.create(
            engine="gpt-35-turbo",
            messages=list(create_messages(question, chat_history)),
            temperature=1.0,
            top_p=1.0,
            n=1,
            stream=stream,
            stop=None,
            max_tokens=16,
            **dict(connection),
        )
    else:
        completion = get_client(connection).chat.completions.create(
            model="gpt-35-turbo",
            messages=list(create_messages(question, chat_history)),
            temperature=1.0,
            top_p=1.0,
            n=1,
            stream=stream,
            stop=None,
            max_tokens=16
        )

    if stream:
        def generator():
            for chunk in completion:
                if chunk.choices:
                    if IS_LEGACY_OPENAI:
                        yield getattr(chunk.choices[0]["delta"], "content", "")
                    else:
                        yield chunk.choices[0].delta.content or ""

        # We must return the generator object, not using yield directly here.
        # Otherwise, the function itself will become a generator, despite whether stream is True or False.
        return generator()
    else:
        # chat api may return message with no content.
        if IS_LEGACY_OPENAI:
            return getattr(completion.choices[0].message, "content", "")
        else:
            return completion.choices[0].message.content or ""
