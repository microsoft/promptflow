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
        assert response["version"] == "20240131.v1"
        assert response["build_info"] == '{"build_number": "20240131.v1"}'

        feature_list = response["feature_list"]
        assert isinstance(feature_list, dict)
        assert all(k == v["name"] for k, v in feature_list.items())
