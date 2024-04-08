from promptflow.core import tool
import random


@tool
def my_python_tool_bkup(idx: int) -> int:
    return idx