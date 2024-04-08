from promptflow.core import tool

@tool
def my_python_tool(input: str) -> str:
    yield "Echo: "
    yield "an input of length "
    yield len(input)
