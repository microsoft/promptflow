from promptflow.core import tool

@tool
def my_python_tool(input: str) -> str:
    yield "Echo: "
    for word in input.split():
        yield word + " "