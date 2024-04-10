from promptflow.core import tool


@tool
def nested_tool(input, recursive_call=True):
    if recursive_call:
        nested_tool(input, recursive_call=False)
    return input
