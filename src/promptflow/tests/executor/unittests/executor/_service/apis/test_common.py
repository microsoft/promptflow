import pytest
from fastapi.testclient import TestClient

from promptflow.executor._service.app import app


@pytest.mark.unittest
class TestCommonApis:
    def setup_method(self):
        self.client = TestClient(app)

    def test_health(self):
        response = self.client.get("/health")
        assert response.status_code == 200
        assert response.text == "healthy"

    def test_version(self, monkeypatch):
        # mock the BUILD_INFO env variable
        monkeypatch.setenv("BUILD_INFO", '{"build_number": "20240131.v1"}')

        response = self.client.get("/version")
        assert response.status_code == 200

        response = response.json()
        assert response["status"] == "healthy"
        assert response["version"] == "promptflow-executor/20240131.v1"
        assert isinstance(response["feature_list"], list)
