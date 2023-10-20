import json

import pytest


@pytest.mark.usefixtures("flow_serving_client_remote_connection")
@pytest.mark.e2etest
def test_serving_api(flow_serving_client_remote_connection):
    response = flow_serving_client_remote_connection.get("/health")
    assert b'{"status":"Healthy","version":"0.0.1"}' in response.data
    response = flow_serving_client_remote_connection.post("/score", data=json.dumps({"text": "hi"}))
    assert (
        response.status_code == 200
    ), f"Response code indicates error {response.status_code} - {response.data.decode()}"
    assert "output_prompt" in json.loads(response.data.decode())
