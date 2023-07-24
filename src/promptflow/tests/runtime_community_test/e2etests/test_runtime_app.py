import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from promptflow.contracts.tool import Tool
from promptflow.exceptions import ErrorResponse
from promptflow.runtime.app import PromptFlowRuntime
from promptflow.runtime.app import create_app as create_runtime_app
from promptflow.utils.utils import get_runtime_version
from promptflow_test.utils import load_and_convert_to_raw

PROMPTFLOW_ROOT = (Path(__file__) / "../../../../").resolve().absolute()
WRONG_REQUESTS_JSON_DATA_ROOT = PROMPTFLOW_ROOT / "tests/test_configs/executor_wrong_requests"
WRONG_REQUESTS_EXPECTED_RESPONSE_ROOT = (
    PROMPTFLOW_ROOT / "tests/test_configs/executor_wrong_requests_expected_responses"
)
EXECUTION_FAILURE_REQUESTS_JSON_DATA_ROOT = PROMPTFLOW_ROOT / "tests/test_configs/runtime_execution_failure_requests"
EXECUTION_FAILURE_EXPECTED_RESPONSE_ROOT = (
    PROMPTFLOW_ROOT / "tests/test_configs/runtime_execution_failure_requests_expected_responses"
)
WRONG_META_REQUESTS_JSON_DATA_ROOT = PROMPTFLOW_ROOT / "tests/test_configs/runtime_wrong_meta_requests"
WRONG_META_REQUESTS_EXPECTED_RESPONSE_ROOT = (
    PROMPTFLOW_ROOT / "tests/test_configs/runtime_wrong_meta_requests_expected_responses"
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


@pytest.mark.e2etest
def test_health(runtime_client):
    # Make a GET request to the health endpoint
    response = runtime_client.get("/health")

    # Check the response
    assert response.status_code == 200
    assert response.json == {"status": "Healthy", "version": "0.0.1"}


@pytest.mark.e2etest
def test_version(runtime_client):
    # Make a GET request to the version endpoint
    response = runtime_client.get("/version")

    # Check the response
    assert response.status_code == 200

    # response.json looks like below, however the number is dynamic
    # So, we don't check the json but compare for some fields inside it
    # assert response.json == {
    #    "build_info": '{"build_number": "ci-promptflow-sdk-test_20230612.55"}',
    #    "status": "Healthy",
    #    "version": "ci-promptflow-sdk-test_20230612.55",
    # }
    assert response.json.get("status") == "Healthy"
    build_info_text = response.json.get("build_info")
    assert build_info_text is not None
    build_info = json.loads(build_info_text)
    assert build_info.get("build_number") == response.json.get("version")
    # The version should be populated to either ci-<build_number> or "local", but not "0.0.1"
    assert build_info.get("build_number") != "0.0.1"


@pytest.mark.e2etest
@pytest.mark.parametrize("path", ["/submit", "/score"])
def test_submit(runtime_client, path):
    payload = {
        "submission_data": {
            "flow": {"tools": [], "nodes": [], "inputs": {}, "outputs": {}},
        },
    }
    headers = {"Content-Type": "application/json"}

    with patch.object(PromptFlowRuntime, "get_instance") as mock_get_instance:
        mock_get_instance.return_value.execute.return_value = {
            "status": "success",
            "output1": "output1_value",
            "output2": "output2_value",
        }

        response = runtime_client.post(path, headers=headers, json=payload)

        mock_get_instance.assert_called_once()

        assert response.status_code == 200
        body = response.json
        error_response = body.pop("errorResponse", None)
        assert body == {
            "status": "success",
            "output1": "output1_value",
            "output2": "output2_value",
        }
        type_and_message = "(ValueError) Neither flow runs or node runs is found in the run result."
        message = f"Failed to parse run result: {type_and_message}"
        assert error_response["error"] == {
            "code": "SystemError",
            "innerError": {
                "code": "RunResultParseError",
                "innerError": None,
            },
            "message": message,
            "messageFormat": "Failed to parse run result: {error_type_and_message}",
            "messageParameters": {
                "error_type_and_message": type_and_message,
            },
            "referenceCode": "Runtime",
        }


@pytest.mark.usefixtures("use_secrets_config_file")
@pytest.mark.e2etest
def test_execution_failure(runtime_client):
    file_name = "qa_with_bing_run_failure.json"
    json_file = EXECUTION_FAILURE_REQUESTS_JSON_DATA_ROOT / file_name
    request_data = load_and_convert_to_raw(source=json_file.resolve(), source_run_id=json_file.stem, as_dict=True)
    headers = {"Content-Type": "application/json"}
    response = runtime_client.post("/submit", headers=headers, json=request_data)

    body = response.json
    assert response.status_code == 200
    expected_message = "Execution failure in 'combine_search_result_1': (ZeroDivisionError) division by zero"
    assert body["errorResponse"]["error"]["message"] == expected_message
    assert body["errorResponse"]["error"]["code"] == "UserError"

    assert len(body["flow_runs"]) == 2
    assert body["flow_runs"][1]["status"] == "Failed"
    assert body["flow_runs"][1]["error"]["message"] == expected_message


@pytest.mark.e2etest
def test_meta(runtime_app):
    client = runtime_app.test_client()

    prompt = """{# This is a answer tool##. #} {# unused #}
You are a chatbot having a conversation with a human.
Given the following extracted parts of a long document and a query, create a final answer with references ("SOURCES").
If you don't know the answer, just say that you don't know. Don't try to make up an answer.
ALWAYS return a "SOURCES" part in your answer.
{{contexts}}
Human: {{query}}"""

    response = client.post(
        "/meta",
        query_string={"tool_type": "prompt", "name": "test_name"},
        data=prompt,
    )

    # Check that the response has a 200 status code
    assert response.status_code == 200
    data = json.loads(response.json)
    assert data["type"] == "prompt"
    assert data["name"] == "test_name"


@pytest.mark.e2etest
def test_meta_v2(runtime_app):
    client = runtime_app.test_client()
    not_exist_file = "not_exist_file.py"
    empty_file = "folder/invalid_tool_empty.py"
    valid_file = "valid_tool.py"
    valid_file_with_dependency = "valid_tool_with_dependency.py"
    no_type_file = "no_type_file.py"
    response = client.post(
        "/meta-v2",
        json={
            "tools": {
                empty_file: {
                    "tool_type": "python",
                },
                valid_file: {
                    "tool_type": "python",
                },
                valid_file_with_dependency: {
                    "tool_type": "python",
                },
                not_exist_file: {
                    "tool_type": "llm",
                },
                no_type_file: {},
            },
            "flow_source_info": {
                "working_dir": str((PROMPTFLOW_ROOT / "tests/test_configs/meta_v2_samples").resolve().absolute()),
                "snapshot_id": None,
            },
        },
    )

    # Check that the response has a 200 status code
    assert response.status_code == 200
    data = response.json
    assert len(data["tools"]) == 2

    def assert_valid_tool(tool, source):
        assert tool.type == "python"
        assert tool.code is None, "Response should not contain code."
        assert tool.source == source

    normal_tool_result = Tool.deserialize(data["tools"][valid_file])
    assert_valid_tool(normal_tool_result, valid_file)
    tool_with_dependency_result = Tool.deserialize(data["tools"][valid_file_with_dependency])
    assert_valid_tool(tool_with_dependency_result, valid_file_with_dependency)

    assert len(data["errors"]) == 3
    empty_file_error = ErrorResponse.from_error_dict(data["errors"][empty_file]["error"])
    assert empty_file_error.error_code_hierarchy == "UserError/ToolValidationError/PythonParsingError/NoToolDefined"
    not_exist_file_error = ErrorResponse.from_error_dict(data["errors"][not_exist_file]["error"])
    assert not_exist_file_error.error_code_hierarchy == "UserError/GenerateMetaUserError/MetaFileNotFound"
    not_exist_file_error = ErrorResponse.from_error_dict(data["errors"][no_type_file]["error"])
    assert not_exist_file_error.error_code_hierarchy == "SystemError/GenerateMetaSystemError/NoToolTypeDefined"


@pytest.mark.e2etest
def test_meta_v2_timeout(runtime_app):
    client = runtime_app.test_client()
    timeout_file = "timeout_tool.py"
    response = client.post(
        "/meta-v2",
        json={
            "tools": {
                timeout_file: {
                    "tool_type": "python",
                }
            },
            "flow_source_info": {
                "working_dir": str((PROMPTFLOW_ROOT / "tests/test_configs/meta_v2_samples").resolve().absolute()),
            },
        },
    )

    # Check that the response has a 200 status code
    assert response.status_code == 200
    data = response.json
    assert len(data["tools"]) == 0

    assert len(data["errors"]) == 1
    empty_file_error = ErrorResponse.from_error_dict(data["errors"][timeout_file]["error"])
    assert empty_file_error.error_code_hierarchy == "UserError/GenerateMetaUserError/GenerateMetaTimeout"


def bad_cases():
    file_to_skip = [
        # skip the following flow runs since they won't fail in submit API
        "property_reference.json",
        "wrong_openai_key.json",
        "output_non_json.json",
        # skip the following flow runs since they don't have proper config to run
        "node_mode_reduce.json",
        "node_mode_missing_inputs.json",
        "wrong_provider.json",
        # skip the following flow runs since it is run failure rather than submission failure
        "tool_code_raises_exception.json",
        "null_connection.json",
        "null_connection2.json",
        "null_connection_param.json",
    ]
    test_dir = Path(WRONG_REQUESTS_JSON_DATA_ROOT).resolve()
    for json_file in test_dir.glob("**/*.json"):
        if json_file.name not in file_to_skip:
            yield json_file.relative_to(test_dir).as_posix()


@pytest.mark.e2etest
@pytest.mark.parametrize("relative_path_to_input_json", bad_cases())
def test_submit_exception(runtime_client, relative_path_to_input_json):
    json_file = WRONG_REQUESTS_JSON_DATA_ROOT / relative_path_to_input_json
    request_data = load_and_convert_to_raw(source=json_file.resolve(), source_run_id=json_file.stem, as_dict=True)
    headers = {"Content-Type": "application/json"}
    response = runtime_client.post("/submit", headers=headers, json=request_data)

    expected_file = (WRONG_REQUESTS_EXPECTED_RESPONSE_ROOT / relative_path_to_input_json).resolve().absolute()

    body = response.json
    body.pop("time", None)
    component_name = body.pop("componentName", None)
    track_back = body.pop("traceback", None)

    # Set this to True to generate expected results as ground truth
    generate_expected_response = False

    if generate_expected_response:
        expected_data = {
            "status_code": response.status_code,
            "body": body,
        }
        expected_file.parent.mkdir(parents=True, exist_ok=True)
        expected_file.write_text(json.dumps(expected_data, indent=4))
    else:
        assert expected_file.exists(), f"Please add test case&result for {json_file.name}"
        expected = json.loads(expected_file.read_text())

        assert expected["status_code"] == response.status_code, track_back
        assert expected["body"] == body
        assert component_name == f"promptflow/{get_runtime_version()}"


def bad_meta_cases():
    test_dir = Path(WRONG_META_REQUESTS_JSON_DATA_ROOT).resolve()
    for json_file in test_dir.glob("**/*.json"):
        yield json_file.relative_to(test_dir).as_posix()


@pytest.mark.e2etest
@pytest.mark.parametrize("relative_path_to_input_json", bad_meta_cases())
def test_meta_exception(runtime_client, relative_path_to_input_json):
    input_file = WRONG_META_REQUESTS_JSON_DATA_ROOT / relative_path_to_input_json
    input_data = json.loads(input_file.read_text())
    response = runtime_client.post(
        "/meta",
        data=input_data["data"],
        query_string={"tool_type": input_data["query_string"]},
    )

    expected_file = WRONG_META_REQUESTS_EXPECTED_RESPONSE_ROOT / relative_path_to_input_json
    body = response.json
    body.pop("time", None)
    component_name = body.pop("componentName", None)
    track_back = body.pop("traceback", None)

    # Set this to True to generate expected results as ground truth
    generate_expected_response = False

    if generate_expected_response:
        expected_data = {
            "status_code": response.status_code,
            "body": body,
        }
        expected_file.parent.mkdir(parents=True, exist_ok=True)
        expected_file.write_text(json.dumps(expected_data, indent=4))
    else:
        assert expected_file.exists(), f"Please add test case&result for {relative_path_to_input_json}"
        expected = json.loads(expected_file.read_text())

        assert expected["status_code"] == response.status_code, track_back
        assert expected["body"] == body
        assert component_name == f"promptflow/{get_runtime_version()}"


@pytest.mark.e2etest
def test_ensure_cases_exist():
    """Use this test case to ensure the test input files exists.

    To make sure that the files will not be accidentically moved or deleted.
    """
    assert list(bad_cases())
    assert list(bad_meta_cases())
