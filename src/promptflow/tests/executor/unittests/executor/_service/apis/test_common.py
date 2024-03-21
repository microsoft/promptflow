import pytest
from fastapi.testclient import TestClient


@pytest.mark.unittest
class TestCommonApis:
    def test_health(self, executor_client: TestClient):
        response = executor_client.get("/health")
        assert response.status_code == 200
        assert response.text == "healthy"

    def test_version(self, monkeypatch, executor_client: TestClient):
        # mock the BUILD_INFO env variable
        monkeypatch.setenv("BUILD_INFO", '{"build_number": "20240131.v1"}')

        response = executor_client.get("/version")
        assert response.status_code == 200

        response = response.json()
        assert response["status"] == "healthy"
        assert response["version"] == "promptflow-executor/20240131.v1"
        assert isinstance(response["feature_list"], list)
