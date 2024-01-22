from promptflow import tool


@tool
def print_input(input: str) -> str:
    return input
