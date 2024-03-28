from typing import Dict, List

from promptflow.core import log_metric, tool


@tool
def aggregate(
    fluency_list: List[float],
    consistency_list: List[float],
    relevance_list: List[float],
    coherence_list: List[float],
) -> Dict[str, float]:
    """
    Takes list of scores for 4 dims and outputs average for them.

    Args:
        fluency_list (List(float)): list of fluency scores
        consistency_list (List(float)): list of consistency scores
        relevance_list (List(float)): list of relevance scores
        coherence_list (List(float)): list of coherence scores

    Returns:
        Dict[str, float]: Returns average scores
    """
    average_fluency = sum(fluency_list) / len(fluency_list)
    average_consistency = sum(consistency_list) / len(consistency_list)
    average_relevance = sum(relevance_list) / len(relevance_list)
    average_coherence = sum(coherence_list) / len(coherence_list)

    log_metric("average_fluency", average_fluency)
    log_metric("average_consistency", average_consistency)
    log_metric("average_relevance", average_relevance)
    log_metric("average_coherence", average_coherence)

    return {
        "average_fluency": average_fluency,
        "average_consistency": average_consistency,
        "average_relevance": average_relevance,
        "average_coherence": average_coherence,
    }
