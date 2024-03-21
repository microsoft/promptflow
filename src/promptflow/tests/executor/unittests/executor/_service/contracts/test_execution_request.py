from pathlib import Path

import pytest

from promptflow.contracts.run_mode import RunMode
from promptflow.executor._service._errors import FlowFilePathInvalid
from promptflow.executor._service.contracts.execution_request import (
    BaseExecutionRequest,
    FlowExecutionRequest,
    NodeExecutionRequest,
)

MOCK_REQUEST = {
    "run_id": "dummy_run_id",
    "working_dir": Path(__file__).parent.as_posix(),
    "flow_file": Path(__file__).as_posix(),
    "output_dir": Path(__file__).parent,
    "log_path": (Path(__file__).parent / "log.txt").as_posix(),
    "node_name": "dummy_node",
}


@pytest.mark.unittest
class TestExecutionRequest:
    def test_get_run_mode(self):
        with pytest.raises(NotImplementedError):
            BaseExecutionRequest(**MOCK_REQUEST).get_run_mode()
        assert FlowExecutionRequest(**MOCK_REQUEST).get_run_mode() == RunMode.Test
        assert NodeExecutionRequest(**MOCK_REQUEST).get_run_mode() == RunMode.SingleNode

    def test_validate_request(self):
        with pytest.raises(FlowFilePathInvalid) as exc_info:
            BaseExecutionRequest(**MOCK_REQUEST).validate_request()
        assert "the flow file path should be relative to the working directory." in exc_info.value.message
