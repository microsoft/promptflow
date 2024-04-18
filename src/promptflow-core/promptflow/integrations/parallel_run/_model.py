# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import json
from dataclasses import dataclass
from typing import Any, Dict, Iterator, Mapping, Optional

from promptflow._utils.utils import DataClassEncoder
from promptflow.contracts.run_info import FlowRunInfo, RunInfo


class Row(Mapping[str, Any]):
    """Row data class."""

    def __init__(self, source: Mapping[str, Any], row_number: int = None):
        self._source = source
        self._rn = row_number

    @property
    def row_number(self) -> int:
        return int(self.get("line_number", self._rn))

    @classmethod
    def from_json(cls, json_str: str, **kwargs) -> "Row":
        return cls.from_dict(d=json.loads(json_str), **kwargs)

    @staticmethod
    def from_dict(d: Dict[str, Any], row_number: int = None) -> "Row":
        return Row(source=d, row_number=row_number)

    def __getitem__(self, __k: str) -> Any:
        return self._source.__getitem__(__k)

    def __len__(self) -> int:
        return self._source.__len__()

    def __iter__(self) -> Iterator[str]:
        return self._source.__iter__()


@dataclass
class DebugInfo:
    run_info: Optional[FlowRunInfo] = None
    node_run_infos: Optional[Mapping[str, RunInfo]] = None


@dataclass
class Result:
    output: Mapping[str, Any]
    aggregation_inputs: Optional[Mapping[str, Any]] = None
    input: Optional[Row] = None
    debug_info: Optional[DebugInfo] = None

    def serialize(self) -> str:
        """Serialize the Result to a JSON string.

        :return: The serialized result
        :rtype: str
        """
        return json.dumps(self, cls=DataClassEncoder)
