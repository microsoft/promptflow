from promptflow.core import tool

@tool
def pass_through(input1: str) -> str:
  return 'hello ' + input1
