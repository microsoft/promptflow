from typing import List
from promptflow import tool


@tool
def aggregate(accuracy_scores: List[float]):
    """
    This tool aggregates the processed result of all lines to the variant level and log metric for each variant.

    :param processed_results: List of the output of line_process node.
    :param variant_ids: List of variant ids that can be used to group the results by variant.
    :param line_numbers: List of line numbers of the variants. If provided, this can be used to
                        group the results by line number.
    """

    aggregated_results = {"accuracy": 0.0, "count": 0}

    # Calculate average accuracy score for each variant
    for i in range(len(accuracy_scores)):
        if accuracy_scores[i]!= None:
            aggregated_results["accuracy"] += accuracy_scores[i]
            aggregated_results["count"] += 1

    if aggregated_results["count"] > 0:
        aggregated_results["accuracy"] /= aggregated_results["count"]

    # Log metric for each variant
    from promptflow import log_metric

    log_metric(key="accuracy", value=aggregated_results["accuracy"])

    return aggregated_results
