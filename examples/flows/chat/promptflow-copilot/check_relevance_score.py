from promptflow.core import tool


@tool
def my_python_tool(score: str) -> str:
    return score == "0"
