# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from enum import Enum


class CommonConstants:
    """Define common constants."""

    DEFAULT_HTTP_TIMEOUT = 60


class RAIService:
    """Define constants related to RAI service"""

    TIMEOUT = 1800
    SLEEP_TIME = 2
    HARM_SEVERITY_THRESHOLD = 4


class HarmSeverityLevel(Enum):
    """Harm severity levels."""

    VeryLow = "Very low"
    Low = "Low"
    Medium = "Medium"
    High = "High"


class Tasks:
    """Defines types of annotation tasks supported by RAI Service."""

    CONTENT_HARM = "content harm"


class EvaluationMetrics:
    """Evaluation metrics for content safety evaluation."""

    HATE_FAIRNESS = "hate_fairness"
    HATE_UNFAIRNESS = "hate_unfairness"
    VIOLENCE = "violence"
    SELF_HARM = "self_harm"
    SEXUAL = "sexual"
