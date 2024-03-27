# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from enum import Enum


class RunMode(str, Enum):
    """An enumeration of possible run modes."""

    Test = "Test"
    SingleNode = "SingleNode"
    Batch = "Batch"

    @classmethod
    def parse(cls, value: str):
        """Parse a string to a RunMode enum value.

        :param value: The string to parse.
        :type value: str
        :return: The corresponding RunMode enum value.
        :rtype: ~promptflow.contracts.run_mode.RunMode
        :raises ValueError: If the value is not a valid string.
        """
        if not isinstance(value, str):
            raise ValueError(f"Invalid value type to parse: {type(value)}")
        if value == "SingleNode":
            return RunMode.SingleNode
        elif value == "Batch":
            return RunMode.Batch
        else:
            return RunMode.Test
