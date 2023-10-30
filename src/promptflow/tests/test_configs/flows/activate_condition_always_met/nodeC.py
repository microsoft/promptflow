from promptflow import tool

# The inputs section will change based on the arguments of the tool function, after you save the code
# Adding type to arguments and return value will help the system show the types properly
# Please update the function name/signature per need
@tool
def my_python_tool(input1: str="Node A not executed.", input2: str="Node B not executed.") -> str:
  return input1 + ' ' + input2
