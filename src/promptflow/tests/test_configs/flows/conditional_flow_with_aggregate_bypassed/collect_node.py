from promptflow.core import tool

@tool
def collect(input1, input2: str="") -> str:
  return {'double': input1, 'square': input2}
