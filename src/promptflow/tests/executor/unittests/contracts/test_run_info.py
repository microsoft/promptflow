from datetime import datetime

import pytest

from promptflow.contracts.run_info import FlowRunInfo, RunInfo, Status


@pytest.mark.unittest
class TestStatus:
    @pytest.mark.parametrize(
        "status,expected",
        [
            (Status.Completed, True),
            (Status.Failed, True),
            (Status.Bypassed, True),
            (Status.Canceled, True),
            (Status.Running, False),
            (Status.Preparing, False),
            (Status.NotStarted, False),
            (Status.CancelRequested, False),
            (123, False),
        ],
    )
    def test_status_is_terminated(self, status, expected):
        assert Status.is_terminated(status) == expected


@pytest.mark.unittest
class TestRunInfo:
    def test_creation(self):
        run_info = RunInfo(
            node="node1",
            flow_run_id="123",
            run_id="123:456",
            status=Status.Running,
            inputs=[],
            output={},
            metrics={},
            error={},
            parent_run_id="789",
            start_time=datetime.now(),
            end_time=datetime.now(),
            system_metrics={},
        )
        assert run_info.node == "node1"
        assert run_info.flow_run_id == "123"
        assert run_info.run_id == "123:456"
        assert run_info.status == Status.Running

    def test_deserialize(self):
        run_info_dict = {
            "node": "get_answer",
            "flow_run_id": "",
            "run_id": "dummy_run_id",
            "status": "Completed",
            "inputs": {"question": "string"},
            "output": "Hello world: What's promptflow?",
            "metrics": None,
            "error": None,
            "parent_run_id": "dummy_flow_run_id",
            "start_time": "2023-11-24T06:03:20.2688262Z",
            "end_time": "2023-11-24T06:03:20.268858Z",
            "index": 0,
            "api_calls": None,
            "cached_run_id": None,
            "cached_flow_run_id": None,
            "logs": None,
            "system_metrics": {"duration": "00:00:00.0000318", "total_tokens": 0},
            "result": "Hello world: What's promptflow?",
        }
        run_info = RunInfo.deserialize(run_info_dict)
        assert run_info.index == 0
        assert isinstance(run_info.start_time, datetime) and isinstance(run_info.end_time, datetime)
        assert run_info.status == Status.Completed
        assert run_info.run_id == "dummy_run_id"
        assert run_info.api_calls is None
        assert run_info.system_metrics == {"duration": "00:00:00.0000318", "total_tokens": 0}
        assert run_info.output == "Hello world: What's promptflow?"


@pytest.mark.unittest
class TestFlowRunInfo:
    def test_creation(self):
        flow_run_info = FlowRunInfo(
            run_id="123:456",
            status=Status.Running,
            error={},
            inputs={},
            output={},
            metrics={},
            request={},
            parent_run_id="789",
            root_run_id="123",
            source_run_id="456",
            flow_id="flow1",
            start_time=datetime.now(),
            end_time=datetime.now(),
            system_metrics={},
            upload_metrics=False,
        )
        assert flow_run_info.run_id == "123:456"
        assert flow_run_info.status == Status.Running
        assert flow_run_info.flow_id == "flow1"

    def test_deserialize(self):
        flow_run_info_dict = {
            "run_id": "dummy_run_id",
            "status": "Completed",
            "error": None,
            "inputs": {"question": "What's promptflow?"},
            "output": {"answer": "Hello world: What's promptflow?"},
            "metrics": None,
            "request": None,
            "parent_run_id": None,
            "root_run_id": None,
            "source_run_id": None,
            "flow_id": "Flow",
            "start_time": "2023-11-23T10:58:37.9436245Z",
            "end_time": "2023-11-23T10:58:37.9590789Z",
            "index": 0,
            "api_calls": None,
            "name": "",
            "description": "",
            "tags": None,
            "system_metrics": {"duration": "00:00:00.0154544", "total_tokens": 0},
            "result": {"answer": "Hello world: What's promptflow?"},
            "upload_metrics": False,
            "otel_trace_id": "test_otel_trace_id",
        }
        flow_run_info = FlowRunInfo.deserialize(flow_run_info_dict)
        assert flow_run_info.index == 0
        assert isinstance(flow_run_info.start_time, datetime) and isinstance(flow_run_info.end_time, datetime)
        assert flow_run_info.status == Status.Completed
        assert flow_run_info.run_id == "dummy_run_id"
        assert flow_run_info.api_calls is None
        assert flow_run_info.system_metrics == {"duration": "00:00:00.0154544", "total_tokens": 0}
        assert flow_run_info.output == {"answer": "Hello world: What's promptflow?"}
        assert flow_run_info.otel_trace_id == "test_otel_trace_id"
