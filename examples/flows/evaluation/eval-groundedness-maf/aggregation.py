from typing import Dict, List


def aggregate(groundedness_scores: List[float]) -> Dict[str, float]:
    count = len(groundedness_scores)
    avg = sum(groundedness_scores) / count if count else 0.0
    return {
        "groundedness": avg,
        "count": count,
    }
