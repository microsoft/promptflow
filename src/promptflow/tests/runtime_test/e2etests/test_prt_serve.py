import json

import pytest

from promptflow._constants import PromptflowEdition
from promptflow.runtime import PromptFlowRuntime


@pytest.mark.usefixtures("enterprise_serving_client")
@pytest.mark.e2etest
def test_runtime_mode(enterprise_serving_client):
    assert enterprise_serving_client is not None
    assert PromptFlowRuntime._instance is not None
    runtime = PromptFlowRuntime.get_instance()
    assert runtime.config.deployment.edition == PromptflowEdition.ENTERPRISE


@pytest.mark.usefixtures("enterprise_serving_client")
@pytest.mark.e2etest
def test_serving_api(enterprise_serving_client):
    response = enterprise_serving_client.get("/health")
    assert b'{"status":"Healthy","version":"0.0.1"}' in response.data
    response = enterprise_serving_client.post("/score", data=json.dumps({"text": "How are you?", "text2": "test"}))
    assert response.status_code == 200
    assert "output_prompt" in json.loads(response.data.decode())
