from promptflow.core import tool


@tool
def echo(input: str) -> str:
    return input
