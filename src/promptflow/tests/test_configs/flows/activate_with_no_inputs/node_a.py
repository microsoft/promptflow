from promptflow.core import tool


@tool
def my_python_tool(input1: str) -> str:
    return 'hello ' + input1
