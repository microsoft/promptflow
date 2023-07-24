import json
import os
from pathlib import Path

import pytest

from promptflow.runtime.app import create_app as create_runtime_app
from promptflow.utils.utils import get_runtime_version
from promptflow_test.utils import load_and_convert_to_raw

PROMPTFLOW_ROOT = (Path(__file__) / "../../../../").resolve().absolute()
RUNTIME_WRONG_REQUESTS_ROOT = PROMPTFLOW_ROOT / "tests/test_configs/runtime_wrong_requests"
RUNTIME_WRONG_REQUESTS_EXPECTED_RESPONSES_ROOT = (
    PROMPTFLOW_ROOT / "tests/test_configs/runtime_wrong_requests_expected_responses"
)


@pytest.fixture(scope="session")
def runtime_app():
    config_file = (PROMPTFLOW_ROOT / "promptflow/runtime/config/dev.yaml").resolve().absolute().as_posix()
    pid = os.getpid()
    app = create_runtime_app(
        config_file,
        args=[
            f"storage.storage_path=data/data_{pid}",
        ],
    )

    app.config.update(
        {
            "TESTING": True,
        }
    )
    yield app


@pytest.fixture(scope="session")
def runtime_client(runtime_app):
    client = runtime_app.test_client()
    yield client


@pytest.mark.usefixtures("use_secrets_config_file")
@pytest.mark.e2etest
def test_submit_exception_runtime_error(runtime_client, invalid_data):
    json_file = RUNTIME_WRONG_REQUESTS_ROOT / "runtime_flow_with_invalid_data.json"
    expected_file = RUNTIME_WRONG_REQUESTS_EXPECTED_RESPONSES_ROOT / "runtime_flow_with_invalid_data.json"
    request_data = load_and_convert_to_raw(source=json_file.resolve(), source_run_id=json_file.stem, as_dict=True)
    # update request_data with invalid data
    request_data["batch_data_input"] = {"data_uri": f"azureml:{invalid_data.id}"}

    headers = {"Content-Type": "application/json"}
    response = runtime_client.post("/submit", headers=headers, json=request_data)

    body = response.json
    body.pop("time", None)
    component_name = body.pop("componentName", None)
    trace_back = body.pop("traceback", None)

    # Update this to True to create ground truth files
    create_expected_response_files = False

    if create_expected_response_files:
        expected_data = {
            "status_code": response.status_code,
            "body": body,
        }
        expected_file.parent.mkdir(parents=True, exist_ok=True)
        expected_file.write_text(json.dumps(expected_data, indent=4))
    else:
        assert expected_file.exists(), "Please add test case&result file."
        expected = json.loads(expected_file.read_text())
        assert response.status_code == expected["status_code"], trace_back
        assert body == expected["body"]
        assert component_name == f"promptflow/{get_runtime_version()}"
