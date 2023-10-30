import base64
import json
import os
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from promptflow import PFClient
from promptflow._sdk._serving.app import create_app as create_serving_app
from promptflow._sdk.entities import AzureOpenAIConnection as AzureOpenAIConnectionEntity
from promptflow._sdk.entities._connection import CustomConnection, _Connection
from promptflow._telemetry.telemetry import TELEMETRY_ENABLED
from promptflow._utils.utils import environment_variable_overwrite

from .recording_utilities import (
    is_recording,
    is_replaying,
    mock_bulkresult_get_openai_metrics,
    mock_flowoperations_test,
    mock_get_local_connections_from_executable,
    mock_persist_node_run,
    mock_toolresolver_resolve_tool_by_node,
    mock_update_run_func,
)

PROMOTFLOW_ROOT = Path(__file__) / "../../.."
RUNTIME_TEST_CONFIGS_ROOT = Path(PROMOTFLOW_ROOT / "tests/test_configs/runtime")
RECORDINGS_TEST_CONFIGS_ROOT = Path(PROMOTFLOW_ROOT / "tests/test_configs/node_recordings").resolve()
CONNECTION_FILE = (PROMOTFLOW_ROOT / "connections.json").resolve().absolute().as_posix()
MODEL_ROOT = Path(PROMOTFLOW_ROOT / "tests/test_configs/flows")


@pytest.fixture(scope="session")
def local_client() -> PFClient:
    # enable telemetry for CI
    with environment_variable_overwrite(TELEMETRY_ENABLED, "true"):
        yield PFClient()


@pytest.fixture(scope="session")
def pf() -> PFClient:
    # enable telemetry for CI
    with environment_variable_overwrite(TELEMETRY_ENABLED, "true"):
        yield PFClient()


@pytest.fixture()
def local_aoai_connection(local_client, azure_open_ai_connection):
    conn = AzureOpenAIConnectionEntity(
        name="azure_open_ai_connection",
        api_key=azure_open_ai_connection.api_key,
        api_base=azure_open_ai_connection.api_base,
    )
    local_client.connections.create_or_update(conn)
    return conn


@pytest.fixture()
def local_alt_aoai_connection(local_client, azure_open_ai_connection):
    conn = AzureOpenAIConnectionEntity(
        name="new_ai_connection",
        api_key=azure_open_ai_connection.api_key,
        api_base=azure_open_ai_connection.api_base,
    )
    local_client.connections.create_or_update(conn)
    return conn


@pytest.fixture()
def local_custom_connection(local_client, azure_open_ai_connection):
    conn = CustomConnection(
        name="test_custom_connection",
        secrets={"test_secret": "test_value"},
    )
    local_client.connections.create_or_update(conn)
    return conn


_connection_setup = False


@pytest.fixture
def setup_local_connection(local_client):
    global _connection_setup
    if is_replaying():
        return
    connection_dict = json.loads(open(CONNECTION_FILE, "r").read())
    for name, _dct in connection_dict.items():
        if _dct["type"] == "BingConnection":
            continue
        local_client.connections.create_or_update(_Connection._from_execution_connection_dict(name=name, data=_dct))
    _connection_setup = True


@pytest.fixture
def flow_serving_client(mocker: MockerFixture):
    model_path = (Path(MODEL_ROOT) / "basic-with-connection").resolve().absolute().as_posix()
    mocker.patch.dict(os.environ, {"PROMPTFLOW_PROJECT_PATH": model_path})
    mocker.patch.dict(os.environ, {"USER_AGENT": "test-user-agent"})
    app = create_serving_app(environment_variables={"API_TYPE": "${azure_open_ai_connection.api_type}"})
    app.config.update(
        {
            "TESTING": True,
        }
    )
    return app.test_client()


@pytest.fixture
def evaluation_flow_serving_client(mocker: MockerFixture):
    model_path = (Path(MODEL_ROOT) / "web_classification").resolve().absolute().as_posix()
    mocker.patch.dict(os.environ, {"PROMPTFLOW_PROJECT_PATH": model_path})
    app = create_serving_app()
    app.config.update(
        {
            "TESTING": True,
        }
    )
    return app.test_client()


def create_client_by_model(model_name: str, mocker: MockerFixture):
    model_path = (Path(MODEL_ROOT) / model_name).resolve().absolute().as_posix()
    mocker.patch.dict(os.environ, {"PROMPTFLOW_PROJECT_PATH": model_path})
    app = create_serving_app()
    app.config.update(
        {
            "TESTING": True,
        }
    )
    return app.test_client()


@pytest.fixture
def serving_client_llm_chat(mocker: MockerFixture):
    return create_client_by_model("chat_flow_with_stream_output", mocker)


@pytest.fixture
def serving_client_python_stream_tools(mocker: MockerFixture):
    return create_client_by_model("python_stream_tools", mocker)


@pytest.fixture
def mock_for_recordings(request: pytest.FixtureRequest, mocker: MockerFixture) -> None:
    """
    mock_for_recordings This is the entrance method of recording/replaying mode.
    environment variables: PF_RECORDING_MODE is the key env var to control this test feature.
    Record: is_recording() will return True, is_replaying() will return False.
        Get node run info (currently llm node), and save the info in the following key value pair
        Key: Ordered dict of all inputs => sha1 hash value
        Value: base64 of output value.
    Replay: is_recording() will return False, is_replaying() will return True.
        hijack all llm nodes with customized tool, it calculate the hash of inputs, and get outputs.
    """
    recording_file: Path = RECORDINGS_TEST_CONFIGS_ROOT / f"{str(request.cls.__name__).lower()}_storage_record.json"
    if is_recording():
        RECORDINGS_TEST_CONFIGS_ROOT.mkdir(parents=True, exist_ok=True)
        mocker.patch(
            "promptflow._sdk.operations._local_storage_operations.LocalStorageOperations.persist_node_run",
            mock_persist_node_run(recording_file),
        )
        mocker.patch(
            "promptflow._sdk.operations._flow_operations.FlowOperations._test",
            mock_flowoperations_test(recording_file),
        )

    if is_replaying():
        mocker.patch(
            "promptflow._core.run_tracker.RunTracker._update_flow_run_info_with_node_runs", mock_update_run_func
        )
        mocker.patch("promptflow.executor._result.BulkResult.get_openai_metrics", mock_bulkresult_get_openai_metrics)

        mocker.patch(
            "promptflow.executor._tool_resolver.ToolResolver.resolve_tool_by_node",
            mock_toolresolver_resolve_tool_by_node(recording_file),
        )
        mocker.patch(
            "promptflow._sdk._utils.get_local_connections_from_executable", mock_get_local_connections_from_executable
        )


@pytest.fixture
def sample_image():
    image_path = (Path(MODEL_ROOT) / "python_tool_with_simple_image" / "logo.jpg").resolve()
    return base64.b64encode(open(image_path, "rb").read()).decode("utf-8")


@pytest.fixture
def serving_client_image_python_flow(mocker: MockerFixture):
    return create_client_by_model("python_tool_with_simple_image", mocker)


@pytest.fixture
def serving_client_composite_image_flow(mocker: MockerFixture):
    return create_client_by_model("python_tool_with_composite_image", mocker)
