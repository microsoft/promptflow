from promptflow.core import tool
import time


@tool
def python_node(input: str, index: int) -> str:
    time.sleep(index + 5)
    return input
