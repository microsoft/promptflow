
from promptflow import tool
from promptflow.tracing import trace


# The inputs section will change based on the arguments of the tool function, after you save the code
# Adding type to arguments and return value will help the system show the types properly
# Please update the function name/signature per need
@tool
def my_python_tool(input1: str) -> str:
    return my_fun(input1)

@trace
def my_fun(input1: str) -> str:
    return "my fun hello" + input1
