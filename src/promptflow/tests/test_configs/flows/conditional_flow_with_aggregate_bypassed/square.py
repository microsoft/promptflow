from promptflow import tool

@tool
def square(input: int) -> int:
  return input*input
