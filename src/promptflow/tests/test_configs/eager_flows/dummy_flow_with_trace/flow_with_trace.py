import asyncio

from promptflow.tracing import trace


@trace
async def wait(n: int):
    await asyncio.sleep(n)


@trace
async def dummy_llm(prompt: str, model: str, wait_seconds: int):
    await wait(wait_seconds)
    return prompt


# 1. In Python, it's not recommended to use `list` as a default argument.
# 2. current tool meta generation logic will return a string instead of a valid json for list default value.
async def my_flow(text: str = "default_text", models: list = None) -> str:
    tasks = []
    if models is None:
        models = ["default_model"]
    for i, model in enumerate(models):
        tasks.append(asyncio.create_task(dummy_llm(text, model, i + 1)))
    await asyncio.wait(tasks)
    return "dummy_output"
