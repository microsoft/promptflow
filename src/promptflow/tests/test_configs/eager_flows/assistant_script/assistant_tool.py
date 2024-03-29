import os

import openai
from openai import AsyncAzureOpenAI
import time

from promptflow.tracing import trace, start_trace


async def my_non_stream_assistant():
    await setup_async_trace()

    client = await get_client()

    assistant = await client.beta.assistants.create(
        name="Math Tutor",
        instructions="You are a personal math tutor. Write and run code to answer math questions.",
        tools=[{"type": "code_interpreter"}],
        model="gpt-4",
    )

    thread = await client.beta.threads.create()

    message = await client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content="I need to solve the equation `3x + 11 = 14`. Can you help me?"
    )

    run = await client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant.id,
        instructions=assistant.instructions
    )

    while run.status in ['queued', 'in_progress', 'cancelling']:
        time.sleep(1)  # Wait for 1 second
        run = await client.beta.threads.runs.retrieve(
            thread_id=thread.id,
            run_id=run.id
        )

    if run.status == 'completed':
        messages = await client.beta.threads.messages.list(
            thread_id=thread.id
        )
        print(message)
    else:
        print(run.dict())


async def get_client():
    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    api_base = os.environ.get("AZURE_OPENAI_ENDPOINT")
    api_version = os.environ.get("OPENAI_API_VERSION")
    client = AsyncAzureOpenAI(
            api_key=api_key,
            api_version=api_version,
            azure_endpoint=api_base,
        )
    return client


async def setup_async_trace():
    openai.resources.beta.assistants.assistants.AsyncAssistants.create= trace(
        openai.resources.beta.assistants.assistants.AsyncAssistants.create)
    openai.resources.beta.threads.threads.AsyncThreads.create = trace(
        openai.resources.beta.threads.threads.AsyncThreads.create)
    openai.resources.beta.threads.messages.messages.AsyncMessages.create = trace(
        openai.resources.beta.threads.messages.messages.AsyncMessages.create)
    openai.resources.beta.threads.runs.runs.AsyncRuns.create = trace(
        openai.resources.beta.threads.runs.runs.AsyncRuns.create)
    openai.resources.beta.threads.runs.runs.AsyncRuns.retrieve = trace(
        openai.resources.beta.threads.runs.runs.AsyncRuns.retrieve)
    openai.resources.beta.threads.messages.messages.AsyncMessages.list = trace(
        openai.resources.beta.threads.messages.messages.AsyncMessages.list)
