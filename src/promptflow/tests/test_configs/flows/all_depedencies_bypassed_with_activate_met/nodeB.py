from promptflow import tool

@tool
def my_python_tool(input1: str="Execution") -> str:
  return input1
