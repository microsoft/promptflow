from promptflow import tool


@tool
def passthrough(input: str):
    return input