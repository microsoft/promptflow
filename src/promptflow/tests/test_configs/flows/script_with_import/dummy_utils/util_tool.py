from promptflow import tool


@tool
def passthrough(x: str):
    return x
