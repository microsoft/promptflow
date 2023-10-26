from promptflow import tool
from promptflow import log_metric

# The inputs section will change based on the arguments of the tool function, after you save the code
# Adding type to arguments and return value will help the system show the types properly
# Please update the function name/signature per need
@tool
def my_python_tool(input1: str, input2:str):
  log_metric("list1_number", input1)
  log_metric("list2_number", input2)
  return input1 + input2
