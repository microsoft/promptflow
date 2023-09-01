from promptflow import tool


@tool
def test(text: str):
    return text + "hello world!"
