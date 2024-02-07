import uuid
from pathlib import Path
from tempfile import mkdtemp
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from promptflow.executor._service.app import app

from .....utils import get_flow_folder


def construct_flow_execution_request_json(flow_folder, inputs=None, connections=None):
    working_dir = get_flow_folder(flow_folder)
    tmp_dir = Path(mkdtemp())
    log_path = tmp_dir / "log.txt"
    return {
        "run_id": str(uuid.uuid4()),
        "working_dir": working_dir.as_posix(),
        "flow_file": "flow.dag.yaml",
        "output_dir": tmp_dir.as_posix(),
        "connections": connections,
        "log_path": log_path.as_posix(),
        "inputs": inputs,
    }


@pytest.mark.unittest
class TestExecutionApis:
    def setup_method(self):
        self.client = TestClient(app)

    def test_flow_execution(self, dev_connections):
        flow_execution_request = construct_flow_execution_request_json(
            flow_folder="print_input_flow",
            inputs={"text": "text_0"},
            connections=dev_connections,
        )
        # run_id = flow_execution_request["run_id"]
        # log_path = Path(flow_execution_request["log_path"])
        with patch("promptflow.executor._service.apis.execution.invoke_function_in_process") as mock:
            mock.side_effect = "mock_result"
            response = self.client.post("/execution/flow", json=flow_execution_request)
            assert response.status_code == 200
