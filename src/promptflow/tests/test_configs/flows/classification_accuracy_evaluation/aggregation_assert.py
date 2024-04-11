from typing import List

from promptflow.core import tool


@tool
def aggregation_assert(input1: List[str], input2: List[str]):
    assert isinstance(input1, list)
    assert isinstance(input2, list)
    assert len(input1) == len(input2)
