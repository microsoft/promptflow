from promptflow import tool


@tool
def echo(input: str) -> str:
    return input
