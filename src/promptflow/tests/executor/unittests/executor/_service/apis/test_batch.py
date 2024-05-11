import pytest
from fastapi.testclient import TestClient


def construct_initialize_request_json():
    return {}


@pytest.mark.unittest
class TestBatchApis:
    def test_initialize(self, executor_client: TestClient):
        response = executor_client.post(url="/batch/initialize")
        assert response.status_code == 200
        assert response.json() == {"status": "success"}
