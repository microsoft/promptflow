import json
from datetime import datetime

import pytest

from promptflow.contracts.run_info import FlowRunInfo, RunInfo, Status
from promptflow.storage.run_records import LineRunRecord, NodeRunRecord
from promptflow.tracing._utils import serialize


@pytest.mark.unittest
def test_line_record():
    start_time = datetime(2023, 7, 12)
    end_time = datetime(2023, 7, 13)
    flow_run_info = FlowRunInfo(
        run_id=None,
        status=Status.Completed,
        error=None,
        inputs=None,
        output=None,
        metrics=None,
        request=None,
        parent_run_id=None,
        root_run_id=None,
        source_run_id=None,
        flow_id=None,
        start_time=start_time,
        end_time=end_time,
        index=0,
    )
    line_record = LineRunRecord.from_run_info(flow_run_info)
    assert line_record.line_number == 0
    assert line_record.start_time == start_time.isoformat()
    assert line_record.end_time == end_time.isoformat()
    assert line_record.status == Status.Completed.value
    assert line_record.run_info == serialize(flow_run_info)


@pytest.mark.unittest
def test_line_serialize():
    start_time = datetime(2023, 7, 12)
    end_time = datetime(2023, 7, 13)
    flow_run_info = FlowRunInfo(
        run_id=None,
        status=Status.Completed,
        error=None,
        inputs=None,
        output=None,
        metrics=None,
        request=None,
        parent_run_id=None,
        root_run_id=None,
        source_run_id=None,
        flow_id=None,
        start_time=start_time,
        end_time=end_time,
        index=0,
    )
    line_record = LineRunRecord.from_run_info(flow_run_info)
    result = line_record.serialize()
    expected_result = json.dumps(line_record.__dict__)
    assert result == expected_result


@pytest.mark.unittest
def test_node_record():
    start_time = datetime(2023, 7, 12)
    end_time = datetime(2023, 7, 13)
    node_run_info = RunInfo(
        node=None,
        run_id=None,
        flow_run_id=None,
        status=Status.Completed,
        inputs=None,
        output=None,
        metrics=None,
        error=None,
        parent_run_id=None,
        start_time=start_time,
        end_time=end_time,
        index=0,
    )
    node_record = NodeRunRecord.from_run_info(node_run_info)
    assert node_record.line_number == 0
    assert node_record.start_time == start_time.isoformat()
    assert node_record.end_time == end_time.isoformat()
    assert node_record.status == Status.Completed.value
    assert node_record.run_info == serialize(node_run_info)


@pytest.mark.unittest
def test_node_serialize():
    start_time = datetime(2023, 7, 12)
    end_time = datetime(2023, 7, 13)
    node_run_info = RunInfo(
        node=None,
        run_id=None,
        flow_run_id=None,
        status=Status.Completed,
        inputs=None,
        output=None,
        metrics=None,
        error=None,
        parent_run_id=None,
        start_time=start_time,
        end_time=end_time,
        index=0,
    )
    node_record = NodeRunRecord.from_run_info(node_run_info)
    result = node_record.serialize()
    expected_result = json.dumps(node_record.__dict__)
    assert result == expected_result
