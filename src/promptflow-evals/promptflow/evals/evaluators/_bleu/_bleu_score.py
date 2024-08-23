# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import random


class BleuScoreEvaluator:
    """
    Evaluator for BLEU score.
    """

    def __init__(self):
        pass

    def __call__(self, *, reference: str, hypothesis: str, **kwargs):
        return {
            "bleu_score": random.random(),
        }
