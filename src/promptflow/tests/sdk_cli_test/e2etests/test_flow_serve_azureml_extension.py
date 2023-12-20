import json
import pytest


@pytest.mark.usefixtures("flow_serving_client_with_encoded_connection")
@pytest.mark.e2etest
def test_azureml_serving_api_with_encoded_connection(flow_serving_client_with_encoded_connection):
    response = flow_serving_client_with_encoded_connection.get("/health")
    assert b'{"status":"Healthy","version":"0.0.1"}' in response.data
    response = flow_serving_client_with_encoded_connection.post("/score", data=json.dumps({"text": "hi"}))
    assert (
        response.status_code == 200
    ), f"Response code indicates error {response.status_code} - {response.data.decode()}"
    assert "output_prompt" in json.loads(response.data.decode())


@pytest.mark.usefixtures("serving_client_with_connection_data_override")
@pytest.mark.e2etest
def test_azureml_serving_api_with_connection_data_override(serving_client_with_connection_data_override):
    response = serving_client_with_connection_data_override.get("/health")
    assert b'{"status":"Healthy","version":"0.0.1"}' in response.data

    response = serving_client_with_connection_data_override.post("/score", data=json.dumps({"text": "hi"}))
    assert (
        response.status_code == 200
    ), f"Response code indicates error {response.status_code} - {response.data.decode()}"
    assert "output_prompt" in json.loads(response.data.decode())
