from promptflow.core import tool

@tool
def square(input: int) -> int:
  return input*input
