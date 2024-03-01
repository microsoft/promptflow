import pytest
from fastapi.testclient import TestClient

from ..utils import construct_flow_execution_request_json


@pytest.mark.usefixtures("dev_connections", "executor_client")
@pytest.mark.e2etest
class TestExecutorServer:
    def test_flow_execution_completed(self, executor_client: TestClient, dev_connections):
        request = construct_flow_execution_request_json("web_classification", connections=dev_connections)
        response = executor_client.post(url="/execution/flow", json=request)
        assert response.status_code == 200

    def test_flow_execution_failed(self, executor_client):
        pass

    def test_flow_execution_error(self, executor_client):
        pass

    def test_node_execution_completed(self, executor_client):
        pass

    def test_node_execution_failed(self, executor_client):
        pass

    def test_node_execution_error(self, executor_client):
        pass

    def test_cancel_execution(self, executor_client):
        pass
