import statistics
from typing import List

from promptflow import tool


@tool
def aggregate_num(num: List[int]) -> int:
    return statistics.mean(num)
