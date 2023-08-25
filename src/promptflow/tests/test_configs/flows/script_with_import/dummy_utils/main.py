from promptflow import tool
from dummy_utils.util_tool import passthrough


@tool
def main(x: str):
    return passthrough(x)
