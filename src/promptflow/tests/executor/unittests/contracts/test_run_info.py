import pytest
from datetime import datetime
from promptflow.contracts.run_info import Status, RunInfo, FlowRunInfo


@pytest.mark.unittest
@pytest.mark.parametrize(
    'status,expected',
    [
        (Status.Completed, True),
        (Status.Failed, True),
        (Status.Bypassed, True),
        (Status.Canceled, True),
        (Status.Running, False),
        (Status.Preparing, False),
        (Status.NotStarted, False),
        (Status.CancelRequested, False),
        (123, False)
    ]
)
def test_status_is_terminated(status, expected):
    assert Status.is_terminated(status) == expected


@pytest.mark.unittest
def test_run_info_creation():
    run_info = RunInfo(
        node='node1',
        flow_run_id='123',
        run_id='123:456',
        status=Status.Running,
        inputs=[],
        output={},
        metrics={},
        error={},
        parent_run_id='789',
        start_time=datetime.now(),
        end_time=datetime.now(),
        system_metrics={}
    )
    assert run_info.node == 'node1'
    assert run_info.flow_run_id == '123'
    assert run_info.run_id == '123:456'
    assert run_info.status == Status.Running


@pytest.mark.unittest
def test_flow_run_info_creation():
    flow_run_info = FlowRunInfo(
        run_id='123:456',
        status=Status.Running,
        error={},
        inputs={},
        output={},
        metrics={},
        request={},
        parent_run_id='789',
        root_run_id='123',
        source_run_id='456',
        flow_id='flow1',
        start_time=datetime.now(),
        end_time=datetime.now(),
        system_metrics={},
        upload_metrics=False
    )
    assert flow_run_info.run_id == '123:456'
    assert flow_run_info.status == Status.Running
    assert flow_run_info.flow_id == 'flow1'
