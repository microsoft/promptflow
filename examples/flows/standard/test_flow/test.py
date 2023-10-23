from promptflow import tool


@tool
def show(text: str):
    return text
