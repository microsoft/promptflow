from promptflow import tool

@tool
def double(input: int) -> int:
  return 2*input
