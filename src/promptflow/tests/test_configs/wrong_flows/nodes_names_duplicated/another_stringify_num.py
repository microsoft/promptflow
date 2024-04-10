from promptflow.core import tool


@tool
def stringify_num(num: int):
    return str(num)
