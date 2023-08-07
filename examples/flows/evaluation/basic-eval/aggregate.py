from typing import List

from promptflow import tool


@tool
def aggregate(processed_results: List[str]):
    """
    This tool aggregates the processed result of all lines to the variant level and log metric for each variant.

    :param processed_results: List of the output of line_process node.
    """

    # Add your aggregation logic here
    # aggregated_results should be a dictionary with the metric name as the key and the metric value as the value.
    # For example: {
    #     "metric_name_0": metric_value_0,
    #     "metric_name_1": metric_value_1,
    #     ...
    # }
    print(len(processed_results))
    print(processed_results)
    aggregated_results = {
        "original_results": processed_results,
    }

    # Log metric for each variant
    from promptflow import log_metric
    log_metric(key="aggregated_results", value=aggregated_results)

    return aggregated_results
