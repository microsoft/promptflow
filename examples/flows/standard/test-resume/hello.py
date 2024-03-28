# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from pathlib import Path
from promptflow import tool

# The inputs section will change based on the arguments of the tool function, after you save the code
# Adding type to arguments and return value will help the system show the types properly
# Please update the function name/signature per need


@tool
def my_python_tool(input1: str) -> str:
    switch_file = Path("wednesday_failure_switch.txt")
    if "Wednesday" in input1:
        if switch_file.exists():
            switch_file.unlink()
            raise Exception("Wednesday failure")
        else:
            switch_file.touch()
    return "Prompt: " + input1
