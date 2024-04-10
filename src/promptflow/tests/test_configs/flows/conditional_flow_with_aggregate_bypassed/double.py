from promptflow.core import tool

@tool
def double(input: int) -> int:
  return 2*input
