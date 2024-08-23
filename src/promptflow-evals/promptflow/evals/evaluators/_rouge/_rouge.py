# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import random
from enum import Enum


class RougeType(str, Enum):
    """
    ROUGE Type.
    """

    ROUGE_1 = "rouge1"
    ROUGE_2 = "rouge2"
    ROUGE_3 = "rouge3"
    ROUGE_4 = "rouge4"
    ROUGE_5 = "rouge5"
    ROUGE_L = "rougeL"


class RougeScoreEvaluator:
    """
    Evaluator for ROUGE score.
    """

    def __init__(self, rouge_type: RougeType):
        pass

    def __call__(self, *, reference: str, hypothesis: str, **kwargs):
        return {
            "rouge_score": random.random(),
        }
