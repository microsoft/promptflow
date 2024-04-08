from promptflow.core import tool, log_metric
from typing import List


@tool
def accuracy(answer: List[str], groundtruth: List[str]):
    assert isinstance(answer, list)
    correct = 0
    for a, g in zip(answer, groundtruth):
        if a == g:
            correct += 1
    accuracy = float(correct) / len(answer)
    log_metric("accuracy", accuracy)
    return accuracy
