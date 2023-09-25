from promptflow import tool


@tool
def print_result(message: str):
    return "Result: " + message
