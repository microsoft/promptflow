from typing import Dict, List


def aggregate(processed_results: List[int]) -> Dict[str, float]:
    num_exception = 0
    num_correct = 0

    for i in range(len(processed_results)):
        if processed_results[i] == -1:
            num_exception += 1
        elif processed_results[i] == 1:
            num_correct += 1

    num_total = len(processed_results)
    accuracy = round(1.0 * num_correct / num_total, 2) if num_total else 0.0
    error_rate = round(1.0 * num_exception / num_total, 2) if num_total else 0.0

    return {
        "num_total": num_total,
        "num_correct": num_correct,
        "num_exception": num_exception,
        "accuracy": accuracy,
        "error_rate": error_rate,
    }
