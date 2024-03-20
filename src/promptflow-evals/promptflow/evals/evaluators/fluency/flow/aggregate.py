from typing import List
from promptflow import tool, log_metric
import numpy as np

@tool
def aggregate(results: List[float]):
    metric_name = "gpt_fluency"
    aggregated_result = round(np.nanmean(results), 2)
    log_metric(key=metric_name, value=aggregated_result)
    return {metric_name: aggregated_result}