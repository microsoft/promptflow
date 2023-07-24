from utils.utils import add
from promptflow import tool


@tool
def my_python_tool(input1: str) -> str:
    return add('Prompt: ', input1)
