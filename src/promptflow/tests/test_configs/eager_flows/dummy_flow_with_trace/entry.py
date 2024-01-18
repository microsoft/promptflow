import asyncio

from promptflow import trace


@trace
async def wait(n: int):
    await asyncio.sleep(n)


@trace
async def dummy_llm(prompt: str, model: str, wait_seconds: int):
    await wait(wait_seconds)
    return prompt


async def my_flow(text: str, models: list = []):
    tasks = []
    for i, model in enumerate(models):
        tasks.append(asyncio.create_task(dummy_llm(text, model, i + 1)))
    await asyncio.wait(tasks)
    return "dummy_output"
