from promptflow import tool
import time

# The inputs section will change based on the arguments of the tool function, after you save the code
# Adding type to arguments and return value will help the system show the types properly
# Please update the function name/signature per need
@tool
def my_python_tool(path: str) -> str:
  content = ""
  try:
    time.sleep(6)
    with open(path, 'r', encoding='utf-16') as file:
      content = file.read()
  except Exception as e:
    with open(path, 'r') as file:
      content = file.read()
  return content


