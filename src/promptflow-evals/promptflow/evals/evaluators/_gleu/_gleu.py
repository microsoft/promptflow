# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import random


class GleuScoreEvaluator:
    """
    Evaluator for GLEU score.
    """

    def __init__(self):
        pass

    def __call__(self, *, reference: str, hypothesis: str, **kwargs):
        return {
            "gleu_score": random.random(),
        }
