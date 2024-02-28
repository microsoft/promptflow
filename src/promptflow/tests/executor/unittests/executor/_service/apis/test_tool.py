import pytest
from fastapi.testclient import TestClient

from promptflow.executor._service.app import app


@pytest.mark.unittest
class TestToolApis:
    def setup_method(self):
        self.client = TestClient(app)

    def test_list_package_tools(self):
        response = self.client.get(url="/tool/package_tools")
        assert response.status_code == 200
        assert response.json()

    def test_gen_tool_meta_all_completed(self):
        pass

    def test_gen_tool_meta_partial_failed(self):
        pass
