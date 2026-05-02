import math
from typing import Any, Dict, List, Optional


def aggregate(
    grounding: List[Optional[float]],
    answer_relevance: List[Optional[float]],
    answer_quality: List[Optional[float]],
    context_precision: List[Optional[float]],
    answer_similarity: List[Optional[float]],
    creativity: List[Optional[float]],
    context_recall: List[Optional[float]],
    answer_correctness: List[Optional[float]],
) -> Dict[str, Any]:
    def _nanmean(values: List[Optional[float]]) -> float:
        valid = []
        for v in values:
            if v is not None:
                try:
                    fv = float(v)
                    if not math.isnan(fv):
                        valid.append(fv)
                except (TypeError, ValueError):
                    pass
        if not valid:
            return float("nan")
        return round(sum(valid) / len(valid), 2)

    all_lists = {
        "grounding": grounding,
        "answer_relevance": answer_relevance,
        "answer_quality": answer_quality,
        "context_precision": context_precision,
        "answer_similarity": answer_similarity,
        "creativity": creativity,
        "context_recall": context_recall,
        "answer_correctness": answer_correctness,
    }
    return {name: _nanmean(values) for name, values in all_lists.items()}
