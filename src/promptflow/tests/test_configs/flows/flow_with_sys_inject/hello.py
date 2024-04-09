import os
import sys

from promptflow.core import tool

sys.path.append(f"{os.path.dirname(__file__)}/custom_lib")
from custom_lib.foo import foo


@tool
def my_python_tool(input1: str) -> str:
    return foo(param=input1)
