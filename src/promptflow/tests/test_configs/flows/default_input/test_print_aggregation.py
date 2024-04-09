from typing import List
from promptflow.core import tool

@tool
def test_print_input(input_str: List[str], input_bool: List[bool], input_list: List[List], input_dict: List[dict]):
    assert input_bool[0] == False
    assert input_list[0] == []
    assert input_dict[0] == {}

    print(input_str)
    return input_str