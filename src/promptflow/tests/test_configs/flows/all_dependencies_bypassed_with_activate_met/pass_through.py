from promptflow.core import tool

@tool
def pass_through(input1: str="Execution") -> str:
    return input1