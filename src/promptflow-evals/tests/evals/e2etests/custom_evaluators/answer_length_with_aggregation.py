from typing import List

import numpy as np


class AnswerLength:
    def __init__(self, *, return_json: bool = False, aggregate_return_json: bool = False):
        self.return_json = return_json
        self.aggregate_return_json = aggregate_return_json

    def __call__(self, answer: str, **kwargs):
        return {"length": len(answer)} if self.return_json else len(answer)

    def __aggregate__(self, line_results: List[str]) -> dict:
        median_value = np.median([v.length for v in line_results]) if self.return_json else np.median(line_results)
        return {"median": median_value} if self.aggregate_return_json else median_value
