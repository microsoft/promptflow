import json

import pytest


@pytest.mark.usefixtures("recording_injection")
@pytest.mark.e2etest
def test_azureml_serving_api_with_encoded_connection(flow_serving_client_with_encoded_connection):
    response = flow_serving_client_with_encoded_connection.get("/health")
    assert b"Healthy" in response.data
    response = flow_serving_client_with_encoded_connection.post("/score", data=json.dumps({"text": "hi"}))
    assert (
        response.status_code == 200
    ), f"Response code indicates error {response.status_code} - {response.data.decode()}"
    assert "output_prompt" in json.loads(response.data.decode())
