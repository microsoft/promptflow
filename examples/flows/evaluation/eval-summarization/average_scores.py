from typing import Dict, List

from promptflow import log_metric, tool


@tool
def aggregate(
    scope: str,
    fluency_list: List[float],
    consistency_list: List[float],
    relevancy_list: List[float],
    coherence_list: List[float],
) -> Dict[str, float]:
    """
    Takes list of scores for 4 dims and outputs average for them.

    Args:
        scope (str): "summary" or "headline" to use for key name in logging
        fluency_list (List(float)): list of fluency scores
        consistency_list (List(float)): list of consistency scores
        relevancy_list (List(float)): list of relevancy scores
        coherence_list (List(float)): list of coherence scores

    Returns:
        Dict[str, float]: Returns average scores
    """

    average_fluency = sum(fluency_list) / len(fluency_list)
    average_consistency = sum(consistency_list) / len(consistency_list)
    average_relevancy = sum(relevancy_list) / len(relevancy_list)
    average_coherence = sum(coherence_list) / len(coherence_list)
    log_metric(f"{scope}_average_fluency", average_fluency)
    log_metric(f"{scope}_average_consistency", average_consistency)
    log_metric(f"{scope}_average_relevancy", average_relevancy)
    log_metric(f"{scope}_average_coherence", average_coherence)

    return {
        f"{scope}_average_fluency": average_fluency,
        f"{scope}_average_consistency": average_consistency,
        f"{scope}_average_relevancy": average_relevancy,
        f"{scope}_average_coherence": average_coherence,
    }
