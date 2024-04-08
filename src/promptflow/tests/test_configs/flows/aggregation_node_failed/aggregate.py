from typing import List
from promptflow.core import tool


@tool
def aggregate(processed_results: List[str]):
    aggregated_results = processed_results
    # raise error to test aggregation node failed
    num = 1/0
    return aggregated_results
