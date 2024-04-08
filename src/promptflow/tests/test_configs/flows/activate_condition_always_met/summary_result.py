from promptflow.core import tool

@tool
def summary_result(input1: str="Node A not executed.", input2: str="Node B not executed.") -> str:
  return input1 + ' ' + input2
