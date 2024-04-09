from promptflow.core import tool


@tool
def passthrough(x: str):
    return x
