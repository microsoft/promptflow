import time
from promptflow.core import tool


@tool
def my_python_tool(chat_history: list, question: str) -> str:

    # sleep for 250ms to simulate OpenAI call
    time.sleep(0.25)
    return "completed"
