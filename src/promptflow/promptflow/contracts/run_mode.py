# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from enum import Enum


class RunMode(str, Enum):
    Test = "Test"
    SingleNode = "SingleNode"
    Batch = "Batch"

    @classmethod
    def parse(cls, value: str):
        """Parse string to RunMode."""
        if not isinstance(value, str):
            raise ValueError(f"Invalid value type to parse: {type(value)}")
        if value == "SingleNode":
            return RunMode.SingleNode
        elif value == "Batch":
            return RunMode.Batch
        else:
            return RunMode.Test
