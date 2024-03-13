from enum import Enum


class TelemetryEventType(str, Enum):
    END = "End"
    START = "Start"

    def __str__(self) -> str:
        return str(self.value)
