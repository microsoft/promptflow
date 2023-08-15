# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from enum import Enum
from typing import Union


class RunMode(int, Enum):
    Flow = 0
    SingleNode = 1
    FromNode = 2
    BulkTest = 3
    Eval = 4

    @classmethod
    def parse(cls, value: Union[str, int]):
        """Parse string to RunMode."""
        if isinstance(value, int):
            return RunMode(value)
        if not isinstance(value, str):
            raise ValueError(f"Invalid value type to parse: {type(value)}")
        if value == "SingleNode":
            return RunMode.SingleNode
        elif value == "FromNode":
            return RunMode.FromNode
        elif value == "BulkTest":
            return RunMode.BulkTest
        elif value == "Eval":
            return RunMode.Eval
        else:
            return RunMode.Flow
