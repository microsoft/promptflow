import asyncio
from time import sleep
from typing import Union

from openai import AsyncAzureOpenAI, AzureOpenAI

from promptflow.contracts.types import PromptTemplate
from promptflow.tracing import trace


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
async def dummy_llm(prompt: str, model: str):
    asyncio.sleep(0.5)
    return "dummy_output"


@trace
async def dummy_llm_tasks_async(prompt: str, models: list):
    tasks = []
    for model in models:
        tasks.append(asyncio.create_task(dummy_llm(prompt, model)))
    done, _ = await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)
    return [task.result() for task in done]


@trace
def render_prompt_template(prompt: PromptTemplate, **kwargs):
    for k, v in kwargs.items():
        prompt = prompt.replace(f"{{{{{k}}}}}", str(v))
    return prompt


@trace
def openai_chat(connection: dict, prompt: str, stream: bool = False):
    client = AzureOpenAI(**connection)

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": prompt}
    ]
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
async def openai_embedding_async(connection: dict, input: Union[str, list]):
    client = AsyncAzureOpenAI(**connection)
    resp = await client.embeddings.create(model="text-embedding-ada-002", input=input)
    return resp.data[0].embedding
