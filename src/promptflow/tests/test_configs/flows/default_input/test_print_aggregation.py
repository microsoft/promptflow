from typing import List
from promptflow import tool

@tool
def test_print_input(inputs: List[str]):
    print(inputs)
    return inputs