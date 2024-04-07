from promptflow import tool


@tool
def hello_world(name: str) -> str:
    return f"Hello World {name}!"
