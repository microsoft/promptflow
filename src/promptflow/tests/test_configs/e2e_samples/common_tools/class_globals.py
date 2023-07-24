from typing import List
from promptflow import tool


class SomeClass:
    val: List


@tool
def class_globals_tool(v: str):
    return v
