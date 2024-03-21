from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from .....utils import construct_flow_execution_request_json, load_content


@pytest.mark.unittest
class TestExecutionApis:
    def test_flow_execution_completed(self, executor_client: TestClient):
        # construct flow execution request
        flow_execution_request = construct_flow_execution_request_json(
            flow_folder="print_input_flow",
            inputs={"text": "text_0"},
        )
        run_id = flow_execution_request["run_id"]
        log_path = Path(flow_execution_request["log_path"])
        # send request
        mock_result = {"result": "mock_result"}
        with patch("promptflow.executor._service.apis.execution.invoke_sync_function_in_process") as mock:
            mock.return_value = mock_result
            response = executor_client.post(url="/execution/flow", json=flow_execution_request)
        # assert response
        assert response.status_code == 200
        assert response.json() == mock_result
        # assert logs
        logs = load_content(log_path)
        keywords_in_log = [
            "execution.service",
            "test-user-agent",
            f"Received flow execution request, flow run id: {run_id}, request id: test-request-id, executor version:",
            f"Completed flow execution request, flow run id: {run_id}.",
        ]
        keywords_not_in_log = [f"Failed to execute flow, flow run id: {run_id}. Error:"]
        assert all(word in logs for word in keywords_in_log)
        assert all(word not in logs for word in keywords_not_in_log)

    def test_cancel_execution(self, executor_client: TestClient):
        request = {"run_id": "test-run-id"}
        response = executor_client.post(url="/execution/cancel", json=request)
        assert response.status_code == 200
        assert response.json() == {"status": "canceled"}
