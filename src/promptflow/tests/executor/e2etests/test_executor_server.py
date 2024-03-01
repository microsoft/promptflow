import pytest


@pytest.mark.usefixtures("dev_connections", "executor_client")
@pytest.mark.e2etest
class TestExecutorServer:
    def test_flow_execution_completed(self, executor_client):
        pass

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
