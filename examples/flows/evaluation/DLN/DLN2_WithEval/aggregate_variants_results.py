from typing import List
from promptflow import tool, log_metric
import numpy as np


@tool
def aggregate_variants_results(results: List[dict]):
    aggregate_results = {}
    
    for d in results:
        # Extract values for the keys
        value = d.get('trainable_prompt_pi_num', 0)
        result_str = d.get('return_result', "").strip().lower()
        
        if value not in aggregate_results:
            aggregate_results[value] = 0
        if '(a)' in result_str:
            # Increase the count for that value in the result dict
            aggregate_results[value] = aggregate_results.get(value, 0) + 1
        
    for name,value in aggregate_results.items():
        log_metric(value, round(aggregate_results[value], 2))
    return aggregate_results
