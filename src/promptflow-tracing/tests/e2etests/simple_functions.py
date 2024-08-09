import asyncio
import re
from time import sleep
from typing import Union

from openai import AsyncAzureOpenAI, AzureOpenAI

from promptflow.tracing import ThreadPoolExecutorWithContext
from promptflow.tracing._trace import trace


@trace
def is_valid_name(name):
    sleep(0.5)
    return len(name) > 0


@trace
def get_user_name(user_id):
    sleep(0.5)
    user_name = f"User {user_id}"
    if not is_valid_name(user_name):
        raise ValueError(f"Invalid user name: {user_name}")

    return user_name


@trace
def format_greeting(user_name):
    sleep(0.5)
    return f"Hello, {user_name}!"


@trace
def greetings(user_id):
    user_name = get_user_name(user_id)
    greeting = format_greeting(user_name)
    return greeting


@trace
async def dummy_llm_async(prompt: str, model: str):
    await asyncio.sleep(0.5)
    return "dummy_output"


@trace
def dummy_llm(prompt: str, model: str):
    sleep(0.5)
    return "dummy_output"


@trace
async def dummy_llm_tasks_async(prompt: str, models: list):
    tasks = []
    for model in models:
        tasks.append(asyncio.create_task(dummy_llm_async(prompt, model)))
    done, _ = await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)
    return [task.result() for task in done]


@trace
def dummy_llm_tasks_threadpool(prompt: str, models: list):
    prompts = [prompt] * len(models)
    with ThreadPoolExecutorWithContext(2, "dummy_llm", initializer=lambda x: x, initargs=(prompt,)) as executor:
        executor.map(dummy_llm, prompts, models)
    with ThreadPoolExecutorWithContext() as executor:
        return list(executor.map(dummy_llm, prompts, models))


@trace
def openai_chat(connection: dict, prompt: str, stream: bool = False):
    client = AzureOpenAI(**connection)

    messages = [{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": prompt}]
    response = client.chat.completions.create(model="gpt-35-turbo", messages=messages, stream=stream)

    if stream:

        def generator():
            for chunk in response:
                if chunk.choices:
                    yield chunk.choices[0].delta.content or ""

        return "".join(generator())
    return response.choices[0].message.content or ""


@trace
def openai_completion(connection: dict, prompt: str, stream: bool = False):
    client = AzureOpenAI(**connection)
    response = client.completions.create(model="text-ada-001", prompt=prompt, stream=stream)

    if stream:

        def generator():
            for chunk in response:
                if chunk.choices:
                    yield chunk.choices[0].text or ""

        return "".join(generator())
    return response.choices[0].text or ""


@trace
async def openai_chat_async(connection: dict, prompt: str, stream: bool = False):
    client = AsyncAzureOpenAI(**connection)

    messages = [{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": prompt}]
    response = await client.chat.completions.create(model="gpt-35-turbo", messages=messages, stream=stream)

    if stream:

        async def generator():
            async for chunk in response:
                if chunk.choices:
                    yield chunk.choices[0].delta.content or ""

        return "".join([chunk async for chunk in generator()])
    return response.choices[0].message.content or ""


@trace
async def openai_completion_async(connection: dict, prompt: str, stream: bool = False):
    client = AsyncAzureOpenAI(**connection)
    response = await client.completions.create(model="text-ada-001", prompt=prompt, stream=stream)

    if stream:

        async def generator():
            async for chunk in response:
                if chunk.choices:
                    yield chunk.choices[0].text or ""

        return "".join([chunk async for chunk in generator()])
    return response.choices[0].text or ""


@trace
async def openai_embedding_async(connection: dict, input: Union[str, list]):
    client = AsyncAzureOpenAI(**connection)
    resp = await client.embeddings.create(model="text-embedding-ada-002", input=input)
    return resp.data[0].embedding


def render(template, **kwargs):
    for key, value in kwargs.items():
        template = template.replace("{{" + key + "}}", str(value))
    return template


@trace
def prompt_tpl_completion(connection: dict, prompt_tpl: str, stream: bool = False, **kwargs):
    client = AzureOpenAI(**connection)
    prompt = render(prompt_tpl, **kwargs)
    response = client.completions.create(model="gpt-35-turbo-instruct", prompt=prompt, stream=stream)

    if stream:

        def generator():
            for chunk in response:
                if chunk.choices:
                    yield chunk.choices[0].text or ""

        return "".join(generator())
    return response.choices[0].text or ""


def parse_chat(chat_str):
    valid_roles = ["system", "user", "assistant", "function"]

    # Split the chat string into chunks based on the role lines
    chunks = re.split(rf"(?i)^\s*#?\s*({'|'.join(valid_roles)})\s*:\s*\n", chat_str, flags=re.MULTILINE)

    chat_list = [
        {"role": chunks[i].strip().lower(), "content": chunks[i + 1].strip()} for i in range(1, len(chunks), 2)
    ]

    return chat_list


@trace
def prompt_tpl_chat(connection: dict, prompt_tpl: str, stream: bool = False, **kwargs):
    client = AzureOpenAI(**connection)
    prompt = render(prompt_tpl, **kwargs)
    messages = parse_chat(prompt)

    response = client.chat.completions.create(model="gpt-35-turbo", messages=messages, stream=stream)

    if stream:

        def generator():
            for chunk in response:
                if chunk.choices:
                    yield chunk.choices[0].delta.content or ""

        return "".join(generator())
    return response.choices[0].message.content or ""
