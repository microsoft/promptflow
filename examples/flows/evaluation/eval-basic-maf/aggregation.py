"""
Aggregation function for eval-basic.

Extracted from the original `aggregate.py` PromptFlow node.
- `@tool` decorator removed (not needed in MAF).
- `log_metric()` replaced with returning metrics as a dict.
"""

from typing import Dict, List


def aggregate(processed_results: List[str]) -> Dict[str, int]:
    """Aggregate per-row results into batch-level metrics.

    :param processed_results: List of "Correct"/"Incorrect" strings from all rows.
    :returns: Dict with metric name → value.
    """
    results_num = len(processed_results)
    correct_num = processed_results.count("Correct")
    return {
        "results_num": results_num,
        "correct_num": correct_num,
    }
