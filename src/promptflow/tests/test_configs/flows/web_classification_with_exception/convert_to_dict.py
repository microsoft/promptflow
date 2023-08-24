
from promptflow import tool


@tool
def convert_to_dict(input_str: str):
    raise Exception("mock exception")
