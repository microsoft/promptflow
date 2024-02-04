import asyncio
import openai
from openai.version import VERSION as OPENAI_VERSION
from typing import List

from promptflow import tool
from promptflow._core.tracer import trace
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

@trace
async def chat(connection: AzureOpenAIConnection, question: str, chat_history: List, model: str) -> str:
    if IS_LEGACY_OPENAI:
        completion = openai.ChatCompletion.create(
            engine=model,
            messages=list(create_messages(question, chat_history)),
            temperature=1.0,
            top_p=1.0,
            n=1,
            stop=None,
            max_tokens=16,
            **dict(connection),
        )
    else:
        completion = get_client(connection).chat.completions.create(
            model=model,
            messages=list(create_messages(question, chat_history)),
            temperature=1.0,
            top_p=1.0,
            n=1,
            stop=None,
            max_tokens=16
        )

    # chat api may return message with no content.
    if IS_LEGACY_OPENAI:
        return getattr(completion.choices[0].message, "content", "")
    else:
        return completion.choices[0].message.content or ""


@tool
async def chat_with_multiple_models(connection: AzureOpenAIConnection, question: str, chat_history: List, models: list):
    tasks = []
    for model in models:
        tasks.append(asyncio.create_task(chat(connection, question, chat_history, model)))
    await asyncio.wait(tasks)
    return "dummy_output"
