from promptflow import tool
import random


@tool
def my_python_tool(idx: int) -> int:
    return idx