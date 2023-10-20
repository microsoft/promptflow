from enum import Enum
from promptflow import tool

class NumEnum(int, Enum):
    Enum1 = 1
    Enum2 = 2
    Enum3 = 3

class StrEnum(str, Enum):
    Enum1 = "string1"
    Enum2 = "string2"
    Enum3 = "string3"

@tool
def my_tool(input_num: NumEnum, input_str: StrEnum, input3: str = "", input4: str = "") -> str:

    return input3 + input4