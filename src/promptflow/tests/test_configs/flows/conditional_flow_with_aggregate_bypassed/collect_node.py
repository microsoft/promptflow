from promptflow import tool

# The inputs section will change based on the arguments of the tool function, after you save the code
# Adding type to arguments and return value will help the system show the types properly
# Please update the function name/signature per need
@tool
def collect(input1: str="", input2: str="") -> str:
  return {'double': input1, 'square': input2}
