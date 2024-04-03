import asyncio
from typing import List

from openai import AsyncAzureOpenAI

from promptflow.core import tool
from promptflow.connections import AzureOpenAIConnection
from promptflow.tracing import trace


def create_messages(question, chat_history):
    yield {"role": "system", "content": "You are a helpful assistant."}
    for chat in chat_history:
        yield {"role": "user", "content": chat["inputs"]["question"]}
        yield {"role": "assistant", "content": chat["outputs"]["answer"]}
        yield {"role": "user", "content": question}


@trace
async def chat(connection: AzureOpenAIConnection, question: str, chat_history: List, model: str) -> str:
    client = AsyncAzureOpenAI(
        api_key=connection.api_key, azure_endpoint=connection.api_base, api_version=connection.api_version
    )
    completion = await client.chat.completions.create(
        model=model,
        messages=list(create_messages(question, chat_history)),
        temperature=1.0,
        top_p=1.0,
        n=1,
        stop=None,
        max_tokens=16
    )
    return completion.choices[0].message.content or ""


@tool
async def chat_with_multiple_models(connection: AzureOpenAIConnection, question: str, chat_history: List, models: list):
    tasks = []
    for model in models:
        tasks.append(asyncio.create_task(chat(connection, question, chat_history, model)))
    done, _ = await asyncio.wait(tasks,  return_when=asyncio.ALL_COMPLETED)
    return [task.result() for task in done]
