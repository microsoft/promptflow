# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json
from dataclasses import dataclass, asdict
from datetime import datetime

from promptflow._utils import serialize
from promptflow.contracts.run_info import FlowRunInfo, RunInfo


@dataclass
class NodeRunRecord:
    """Data class for storing the run record of each node during single line execution on the flow

    Attributes:
        node_name (str): The name of the node.
        line_number (int): The line number in the source file.
        run_info (str): The information about the run.
        start_time (datetime): The time the node started running.
        end_time (datetime): The time the node finished running.
        status (str): The status of the node run.
    """
    node_name: str
    line_number: int
    run_info: str
    start_time: datetime
    end_time: datetime
    status: str

    @staticmethod
    def from_run_info(run_info: RunInfo) -> "NodeRunRecord":
        """Create a NodeRunRecord from a RunInfo object.

        Parameters:
            run_info (RunInfo): The run info to create the NodeRunRecord from.

        Returns:
            NodeRunRecord: The created NodeRunRecord.
        """
        return NodeRunRecord(
            node_name=run_info.node,
            line_number=run_info.index,
            run_info=serialize(run_info),
            start_time=run_info.start_time.isoformat(),
            end_time=run_info.end_time.isoformat(),
            status=run_info.status.value,
        )

    def serialize(node_record: "NodeRunRecord") -> str:
        """Serialize the NodeRunRecord for storage in blob.

        Parameters:
            node_record (NodeRunRecord): The NodeRunRecord to serialize.

        Returns:
            str: The serialized result.
        """
        return json.dumps(asdict(node_record))


@dataclass
class LineRunRecord:
    """Data class for storing the run record of single line execution on the flow.

    Attributes:
        line_number (int): The line number in the record.
        run_info (str): The information about the line run.
        start_time (datetime): The time the line started executing.
        end_time (datetime): The time the line finished executing.
        name (str): The name of the line.
        description (str): The description of the line.
        status (str): The status of the line execution.
        tags (str): The tags associated with the line.
    """
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
        """Create a LineRunRecord from a FlowRunInfo object.

        Parameters:
            run_info (FlowRunInfo): The run info to create the LineRunRecord from.

        Returns:
            LineRunRecord: The created LineRunRecord.
        """
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
        """Serialize the LineRunRecord for storage in blob.

        Parameters:
            line_record (LineRunRecord): The LineRunRecord to serialize.

        Returns:
            str: The serialized result.
        """
        return json.dumps(asdict(line_record))
