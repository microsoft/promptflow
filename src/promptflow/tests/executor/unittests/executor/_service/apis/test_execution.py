import uuid
from pathlib import Path
from tempfile import mkdtemp
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from promptflow.executor._service.app import app

from .....utils import get_flow_folder, load_content


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

    def test_flow_execution_completed(self):
        # construct flow execution request
        flow_execution_request = construct_flow_execution_request_json(
            flow_folder="print_input_flow",
            inputs={"text": "text_0"},
        )
        run_id = flow_execution_request["run_id"]
        log_path = Path(flow_execution_request["log_path"])
        # send request
        mock_result = {"result": "mock_result"}
        with patch("promptflow.executor._service.apis.execution.invoke_function_in_process") as mock:
            mock.return_value = mock_result
            response = self.client.post(
                url="/execution/flow", json=flow_execution_request, headers={"context-request-id": "test-request-id"}
            )
        # assert response
        assert response.status_code == 200
        assert response.json() == mock_result
        # assert logs
        logs = load_content(log_path)
        keywords_in_log = [
            "execution.service",
            f"Received flow execution request, flow run id: {run_id}, request id: test-request-id, executor version:",
            f"Completed flow execution request, flow run id: {run_id}.",
        ]
        keywords_not_in_log = [f"Failed to execute flow, flow run id: {run_id}. Error:"]
        assert all(word in logs for word in keywords_in_log)
        assert all(word not in logs for word in keywords_not_in_log)
