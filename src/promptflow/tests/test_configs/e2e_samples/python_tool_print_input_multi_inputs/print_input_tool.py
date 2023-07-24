from promptflow import tool


@tool
def print_inputs(
    text_1: str = None,
    text_2: str = None,
    text_3: str = None,
):
    return text_1 + text_2 + text_3