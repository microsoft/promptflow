from typing import Dict, List


def aggregate(
    coherence: List[float],
    consistency: List[float],
    fluency: List[float],
    relevance: List[float],
) -> Dict[str, float]:
    average_fluency = sum(fluency) / len(fluency) if fluency else 0.0
    average_consistency = sum(consistency) / len(consistency) if consistency else 0.0
    average_relevance = sum(relevance) / len(relevance) if relevance else 0.0
    average_coherence = sum(coherence) / len(coherence) if coherence else 0.0
    return {
        "average_fluency": average_fluency,
        "average_consistency": average_consistency,
        "average_relevance": average_relevance,
        "average_coherence": average_coherence,
    }
