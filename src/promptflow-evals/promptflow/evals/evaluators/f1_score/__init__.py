# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

__path__ = __import__("pkgutil").extend_path(__path__, __name__)  # type: ignore

from .f1_score import F1ScoreEvaluator

__all__ = [
    "F1ScoreEvaluator",
]
