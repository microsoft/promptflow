import pytest
from fastapi.testclient import TestClient

from promptflow._utils.exception_utils import ErrorResponse, ResponseCode
from promptflow.contracts.run_info import Status
from promptflow.executor._result import LineResult

from ..utils import WRONG_FLOW_ROOT, construct_flow_execution_request_json


@pytest.mark.usefixtures("dev_connections", "executor_client")
@pytest.mark.e2etest
class TestExecutorServer:
    def test_flow_execution_completed(self, executor_client: TestClient, dev_connections):
        flow_folder = "web_classification"
        request = construct_flow_execution_request_json(flow_folder, connections=dev_connections)
        response = executor_client.post(url="/execution/flow", json=request)
        assert response.status_code == 200
        line_result = LineResult.deserialize(response.json())
        assert line_result.run_info.status == Status.Completed
        assert line_result.output is not None
        assert len(line_result.node_run_infos) == 5
        assert all(node_run_info.status == Status.Completed for node_run_info in line_result.node_run_infos.values())

    def test_flow_execution_failed(self, executor_client: TestClient):
        pass

    def test_flow_execution_error(self, executor_client: TestClient):
        flow_folder = "node_circular_dependency"
        request = construct_flow_execution_request_json(flow_folder, WRONG_FLOW_ROOT)
        response = executor_client.post(url="/execution/flow", json=request)
        assert response.status_code == 400
        error_resp_json = response.json()
        assert "test-user-agent" in error_resp_json["componentName"]
        error_response = ErrorResponse.from_error_dict(error_resp_json["error"])
        assert error_response.response_code == ResponseCode.CLIENT_ERROR

    def test_node_execution_completed(self, executor_client: TestClient):
        pass

    def test_node_execution_failed(self, executor_client: TestClient):
        pass

    def test_node_execution_error(self, executor_client: TestClient):
        pass

    def test_cancel_execution(self, executor_client: TestClient):
        pass
