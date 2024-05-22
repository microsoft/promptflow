class RAIService:
    """Define constants related to RAI service"""

    TIMEOUT = 1800
    SLEEP_TIME = 2


class Tasks:
    """Defines types of annotation tasks supported by RAI Service."""

    GROUNDEDNESS = "groundedness"


class EvaluationMetrics:
    GROUNDEDNESS = "generic_groundedness"
