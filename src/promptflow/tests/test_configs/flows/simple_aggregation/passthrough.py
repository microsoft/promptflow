from promptflow.core import tool


@tool
def passthrough(input: str):
    return input