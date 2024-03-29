from typing import List
from promptflow.core import tool


@tool
def aggregate(perceived_intelligence_score: List[float]):
    aggregated_results = {"perceived_intelligence_score": 0.0, "count": 0}

    # Calculate average perceived_intelligence_score
    for i in range(len(perceived_intelligence_score)):
        aggregated_results["perceived_intelligence_score"] += perceived_intelligence_score[i]
        aggregated_results["count"] += 1

    aggregated_results["perceived_intelligence_score"] /= aggregated_results["count"]

    # Log metric for each variant
    from promptflow.core import log_metric

    log_metric(key="perceived_intelligence_score", value=aggregated_results["perceived_intelligence_score"])

    return aggregated_results
