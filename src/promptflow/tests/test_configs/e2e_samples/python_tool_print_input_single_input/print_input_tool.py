from promptflow import tool


@tool
def print_inputs(
    text_1: str = None,
):
    return text_1