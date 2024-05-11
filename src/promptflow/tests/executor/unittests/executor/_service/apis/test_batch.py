import pytest
from fastapi.testclient import TestClient

from .....utils import construct_initialization_request_json


def construct_initialize_request_json():
    return {}


@pytest.mark.unittest
class TestBatchApis:
    @pytest.mark.parametrize(
        "flow_folder, flow_file, expected_inputs_definition, expected_has_aggregation",
        [
            (),
        ],
    )
    def test_initialize(
        self, executor_client: TestClient, flow_folder, flow_file, expected_inputs_definition, expected_has_aggregation
    ):
        initialization_request = construct_initialization_request_json(
            flow_folder=flow_folder,
            flow_file=flow_file,
        )
        response = executor_client.post(url="/batch/initialize", json=initialization_request)
        # assert response
        assert response.status_code == 200
        assert response.json() == {
            "inputs_definition": expected_inputs_definition,
            "has_aggregation": expected_has_aggregation,
        }
