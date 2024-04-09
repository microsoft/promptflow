from promptflow.core import tool


@tool
def test(text: str):
    return text + "hello world!"
