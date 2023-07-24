from promptflow import tool


@tool
def passthrough(val: str) -> str:
    return val
