# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json
from dataclasses import dataclass, asdict
from datetime import datetime

from promptflow._internal import serialize
from promptflow.contracts.run_info import FlowRunInfo, RunInfo


@dataclass
class NodeRunRecord:
    NodeName: str
    line_number: int
    run_info: str
    start_time: datetime
    end_time: datetime
    status: str

    @staticmethod
    def from_run_info(run_info: RunInfo) -> "NodeRunRecord":
        return NodeRunRecord(
            NodeName=run_info.node,
            line_number=run_info.index,
            run_info=serialize(run_info),
            start_time=run_info.start_time.isoformat(),
            end_time=run_info.end_time.isoformat(),
            status=run_info.status.value,
        )

    def serialize(node_record: "NodeRunRecord") -> str:
        return json.dumps(asdict(node_record))


@dataclass
class LineRunRecord:
    line_number: int
    run_info: str
    start_time: datetime
    end_time: datetime
    name: str
    description: str
    status: str
    tags: str

    @staticmethod
    def from_run_info(run_info: FlowRunInfo) -> "LineRunRecord":
        return LineRunRecord(
            line_number=run_info.index,
            run_info=serialize(run_info),
            start_time=run_info.start_time.isoformat(),
            end_time=run_info.end_time.isoformat(),
            name=run_info.name,
            description=run_info.description,
            status=run_info.status.value,
            tags=run_info.tags,
        )

    def serialize(line_record: "LineRunRecord") -> str:
        return json.dumps(asdict(line_record))
