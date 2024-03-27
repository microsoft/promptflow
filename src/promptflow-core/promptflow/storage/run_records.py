# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json
from dataclasses import asdict, dataclass
from datetime import datetime

from promptflow.contracts.run_info import FlowRunInfo, RunInfo
from promptflow.tracing._utils import serialize


@dataclass
class NodeRunRecord:
    """Dataclass for storing the run record of each node during single line execution on the flow

    :param str node_name: The name of the node
    :param int line_number: The line number in the source file
    :param dict run_info: The information about the run
    :param datetime start_time: The time the node started running
    :param datetime end_time: The time the node finished running
    :param str status: The status of the node run
    """

    node_name: str
    line_number: int
    run_info: dict
    start_time: datetime
    end_time: datetime
    status: str

    @staticmethod
    def from_run_info(run_info: RunInfo) -> "NodeRunRecord":
        """Create a NodeRunRecord from a RunInfo object.

        :param RunInfo run_info: The run info to create the NodeRunRecord from
        :return: The created NodeRunRecord
        :rtype: NodeRunRecord
        """
        return NodeRunRecord(
            node_name=run_info.node,
            line_number=run_info.index,
            run_info=serialize(run_info),
            start_time=run_info.start_time.isoformat(),
            end_time=run_info.end_time.isoformat(),
            status=run_info.status.value,
        )

    def serialize(self) -> str:
        """Serialize the NodeRunRecord for storage in blob.

        :return: The serialized result
        :rtype: str
        """
        return json.dumps(asdict(self))


@dataclass
class LineRunRecord:
    """A dataclass for storing the run record of a single line execution on the flow.

    :param int line_number: The line number in the record
    :param dict run_info: The information about the line run
    :param datetime start_time: The time the line started executing
    :param datetime end_time: The time the line finished executing
    :param str name: The name of the line run
    :param str description: The description of the line run
    :param str status: The status of the line execution
    :param str tags: The tags associated with the line run
    """

    line_number: int
    run_info: dict
    start_time: datetime
    end_time: datetime
    name: str
    description: str
    status: str
    tags: str

    @staticmethod
    def from_run_info(run_info: FlowRunInfo) -> "LineRunRecord":
        """Create a LineRunRecord from a FlowRunInfo object.

        :param FlowRunInfo run_info: The run info to create the LineRunRecord from
        :return: The created LineRunRecord
        :rtype: LineRunRecord
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

    def serialize(self) -> str:
        """Serialize the LineRunRecord for storage in a blob.

        :return: The serialized result
        :rtype: str
        """
        return json.dumps(asdict(self))
