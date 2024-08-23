# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import random


class MeteorScoreEvaluator:
    """
    Evaluator for METEOR score.
    """

    def __init__(self, alpha: float = 0.9, beta: float = 3.0, gamma: float = 0.5):
        pass

    def __call__(self, *, reference: str, hypothesis: str, **kwargs):
        return {
            "meteor_score": random.random(),
        }
