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
    PROTECTED_MATERIAL = "protected material"


class _InternalTasks:
    """Defines types of annotation tasks that are supported for internal use."""

    ELECTION_CRITICAL_INFORMATION = "election critical information"


class EvaluationMetrics:
    """Evaluation metrics to aid the RAI service in determining what
    metrics to request, and how to present them back to the user."""

    HATE_FAIRNESS = "hate_fairness"
    HATE_UNFAIRNESS = "hate_unfairness"
    VIOLENCE = "violence"
    SELF_HARM = "self_harm"
    SEXUAL = "sexual"
    PROTECTED_MATERIAL = "protected_material"


class _InternalEvaluationMetrics:
    """Evaluation metrics that are not publicly supported."""

    ELECTION_CRITICAL_INFORMATION = "election_critical_information"
