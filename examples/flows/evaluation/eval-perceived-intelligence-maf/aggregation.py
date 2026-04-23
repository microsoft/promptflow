from typing import Dict, List


def aggregate(perceived_intelligence_scores: List[float]) -> Dict[str, float]:
    count = len(perceived_intelligence_scores)
    avg = sum(perceived_intelligence_scores) / count if count else 0.0
    return {
        "perceived_intelligence_score": avg,
        "count": count,
    }
