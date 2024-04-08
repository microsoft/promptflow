import os
import openai

from dotenv import load_dotenv
from promptflow.core import tool

# The inputs section will change based on the arguments of the tool function, after you save the code
# Adding type to arguments and return value will help the system show the types properly
# Please update the function name/signature per need


def to_bool(value) -> bool:
    return str(value).lower() == "true"


@tool
def my_python_tool(input1: str) -> str:
  return 'hello '
