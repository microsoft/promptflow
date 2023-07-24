from typing import Union
from enum import Enum


class RunMode(int, Enum):
    Flow = 0
    SingleNode = 1
    FromNode = 2
    BulkTest = 3
    Eval = 4

    @property
    def persist_node_run(self):
        """For some mode, node run result should be persisted."""
        return self not in (RunMode.SingleNode, RunMode.FromNode)

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
