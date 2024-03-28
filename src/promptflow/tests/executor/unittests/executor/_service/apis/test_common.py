import pytest
from fastapi.testclient import TestClient

from promptflow._version import VERSION


@pytest.mark.unittest
class TestCommonApis:
    def test_health(self, executor_client: TestClient):
        response = executor_client.get("/health")
        assert response.status_code == 200
        assert response.text == "healthy"

    def test_version(self, monkeypatch, executor_client: TestClient):
        # mock the BUILD_INFO env variable
        monkeypatch.setenv("BUILD_INFO", '{"commit_id": "test-commit-id"}')

        response = executor_client.get("/version")
        assert response.status_code == 200

        response = response.json()
        assert response["status"] == "healthy"
        assert response["version"] == VERSION
        assert response["commit_id"] == "test-commit-id"
        assert isinstance(response["feature_list"], list)
