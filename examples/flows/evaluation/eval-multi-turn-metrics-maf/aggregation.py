import math
from typing import Any, Dict, List, Optional


def aggregate(
    answer_relevance: List[Optional[float]],
    conversation_quality: List[Optional[float]],
    creativity: List[Optional[float]],
    grounding: List[Optional[float]],
) -> Dict[str, Any]:
    def _nanmean(values: List[Optional[float]]) -> float:
        valid = [v for v in values if v is not None and not (isinstance(v, float) and math.isnan(v))]
        if not valid:
            return float("nan")
        return round(sum(valid) / len(valid), 2)

    metrics = {}
    all_lists = {
        "answer_relevance": answer_relevance,
        "conversation_quality": conversation_quality,
        "creativity": creativity,
        "grounding": grounding,
    }
    for name, values in all_lists.items():
        avg = _nanmean(values)
        metrics[name] = avg

    return metrics
