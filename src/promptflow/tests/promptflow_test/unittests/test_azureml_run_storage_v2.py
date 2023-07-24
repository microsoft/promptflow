from datetime import datetime

import pytest

from promptflow.contracts.run_info import FlowRunInfo, RunInfo, Status
from promptflow.storage.azureml_run_storage_v2 import FlowRecords, IntermediateRunRecords
from promptflow.utils.dataclass_serializer import serialize


@pytest.mark.unittest
def test_flow_records():
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
        variant_id=None,
    )
    flow_record = FlowRecords.from_run_info(flow_run_info)
    assert flow_record.line_number == 0
    assert flow_record.start_time == start_time.isoformat()
    assert flow_record.end_time == end_time.isoformat()
    assert flow_record.status == Status.Completed.value
    assert flow_record.run_info == serialize(flow_run_info)


@pytest.mark.unittest
def test_intermediate_run_records():
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
    node_record = IntermediateRunRecords.from_run_info(node_run_info)
    assert node_record.line_number == 0
    assert node_record.start_time == start_time.isoformat()
    assert node_record.end_time == end_time.isoformat()
    assert node_record.status == Status.Completed.value
    assert node_record.run_info == serialize(node_run_info)
