from difflib import SequenceMatcher
from promptflow.core import tool


@tool
def similarity(answer, ground_truth):
    return SequenceMatcher(None, answer, ground_truth).ratio()
