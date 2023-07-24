from promptflow import tool
from common_tools.class_globals import class_globals_tool


@tool
def try_import_tool(v: str):
    return class_globals_tool(v)
