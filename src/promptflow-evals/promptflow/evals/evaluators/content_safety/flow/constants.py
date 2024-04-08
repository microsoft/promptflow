from enum import Enum


class RAIService:
    """Define constants related to RAI service"""
    TIMEOUT = 1800
    SLEEP_TIME = 2
    HARM_SEVERITY_THRESHOLD = 4


class HarmSeverityLevel(Enum):
    Safe = 0
    Low = 1
    Medium = 2
    High = 3


class Tasks:
    """Defines types of annotation tasks supported by RAI Service."""
    CONTENT_HARM = "content harm"
