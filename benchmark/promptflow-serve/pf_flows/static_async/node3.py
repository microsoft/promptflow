import asyncio
from promptflow.core import tool


@tool
async def my_python_tool(chat_history: list, question: str) -> str:

    # sleep for 250ms to simulate OpenAI call async
    await asyncio.sleep(0.25)
    return "completed"
