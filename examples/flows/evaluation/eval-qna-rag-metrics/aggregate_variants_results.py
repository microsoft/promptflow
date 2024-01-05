from typing import List
from promptflow import tool, log_metric
import numpy as np


@tool
def aggregate_variants_results(results: List[dict], metrics: List[str]):
    aggregate_results = {}
    for result in results:
        for name, value in result.items():
            if name not in aggregate_results.keys():
                aggregate_results[name] = []
            try:
                float_val = float(value)
            except Exception:
                float_val = np.nan
            aggregate_results[name].append(float_val)

    for name, value in aggregate_results.items():
        if name in metrics[0]:
            metric_name = name
            aggregate_results[name] = np.nanmean(value)
            if 'pass_rate' in metric_name:
                metric_name = metric_name + "(%)"
                aggregate_results[name] = aggregate_results[name] * 100.0
            aggregate_results[name] = round(aggregate_results[name], 2)
            log_metric(metric_name, aggregate_results[name])

    return aggregate_results
