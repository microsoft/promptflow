# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from typing import List

from promptflow.core import log_metric, tool


@tool
def aggregate(processed_results: List[str]):
    """
    This tool aggregates the processed result of all lines and calculate the accuracy. Then log metric for the accuracy.

    :param processed_results: List of the output of line_process node.
    """

    # Add your aggregation logic here
    # Aggregate the results of all lines and calculate the accuracy
    aggregated_result = round((processed_results.count("Correct") / len(processed_results)), 2)

    # Log metric the aggregate result
    log_metric(key="accuracy", value=aggregated_result)

    return aggregated_result
