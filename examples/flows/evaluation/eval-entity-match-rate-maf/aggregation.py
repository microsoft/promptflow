from typing import Dict, List


def aggregate(exact_match: List[int], partial_match: List[int],
              answer: List[list], ground_truth: List[list]) -> Dict[str, float]:
    n = len(exact_match)
    exact_match_rate = sum(exact_match) / n if n else 0.0
    partial_match_rate = sum(partial_match) / n if n else 0.0
    return {
        "exact_match_rate": exact_match_rate,
        "partial_match_rate": partial_match_rate,
    }
