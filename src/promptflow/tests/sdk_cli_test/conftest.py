import base64
import json
import os
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from promptflow import PFClient
from promptflow._core.flow_execution_context import FlowExecutionContext
from promptflow._sdk._serving.app import create_app as create_serving_app
from promptflow._sdk.entities import AzureOpenAIConnection as AzureOpenAIConnectionEntity
from promptflow._sdk.entities._connection import CustomConnection, _Connection

from .recording_utilities import RecordFileMissingException, RecordItemMissingException, RecordStorage

PROMOTFLOW_ROOT = Path(__file__) / "../../.."
RUNTIME_TEST_CONFIGS_ROOT = Path(PROMOTFLOW_ROOT / "tests/test_configs/runtime")
RECORDINGS_TEST_CONFIGS_ROOT = Path(PROMOTFLOW_ROOT / "tests/test_configs/node_recordings").resolve()
CONNECTION_FILE = (PROMOTFLOW_ROOT / "connections.json").resolve().absolute().as_posix()
MODEL_ROOT = Path(PROMOTFLOW_ROOT / "tests/test_configs/flows")


@pytest.fixture(scope="session")
def local_client() -> PFClient:
    yield PFClient()


@pytest.fixture(scope="session")
def pf() -> PFClient:
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
def setup_local_connection(local_client, azure_open_ai_connection):
    global _connection_setup
    if _connection_setup:
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
def sample_image():
    image_path = (Path(MODEL_ROOT) / "python_tool_with_simple_image" / "logo.jpg").resolve()
    return base64.b64encode(open(image_path, "rb").read()).decode("utf-8")


@pytest.fixture
def serving_client_image_python_flow(mocker: MockerFixture):
    return create_client_by_model("python_tool_with_simple_image", mocker)


@pytest.fixture
def serving_client_composite_image_flow(mocker: MockerFixture):
    return create_client_by_model("python_tool_with_composite_image", mocker)


def mock_origin(original):
    def mock_invoke_tool(self, node, func, kwargs):
        if type(func).__name__ == "partial":
            func_wo_partial = func.func
        else:
            func_wo_partial = func

        if (
            node.provider == "AzureOpenAI"
            or node.provider == "OpenAI"
            or func_wo_partial.__qualname__.startswith("AzureOpenAI")
            or func_wo_partial.__qualname__.startswith("OpenAI")
            or func_wo_partial.__qualname__ == "fetch_text_content_from_url"
            or func_wo_partial.__qualname__ == "my_python_tool"
        ):
            input_dict = {}
            for key in kwargs:
                input_dict[key] = kwargs[key]
            if type(func).__name__ == "partial":
                input_dict["_args"] = func.args
                for key in func.keywords:
                    input_dict[key] = func.keywords[key]
            else:
                input_dict["_args"] = []
            input_dict["_func"] = func_wo_partial.__qualname__
            # Replay mode will direct return item from record file
            if RecordStorage.is_replaying_mode():
                obj = RecordStorage.get_instance().get_record(input_dict)
                return obj

            # Record mode will record item to record file
            if RecordStorage.is_recording_mode():
                # If already recorded, use previous result
                # If record item missing, call related functions and record result
                try:
                    obj = RecordStorage.get_instance().get_record(input_dict)
                except (RecordItemMissingException, RecordFileMissingException):
                    obj_original = original(self, node, func, kwargs)
                    obj = RecordStorage.get_instance().set_record(input_dict, obj_original)
                # More exceptions should just raise
            else:
                obj = original(self, node, func, kwargs)
            return obj
        return original(self, node, func, kwargs)

    return mock_invoke_tool


@pytest.fixture
def recording_file_override(request: pytest.FixtureRequest, mocker: MockerFixture):
    if RecordStorage.is_replaying_mode() or RecordStorage.is_recording_mode():
        file_path = RECORDINGS_TEST_CONFIGS_ROOT / "node_cache.shelve"
        RecordStorage.get_instance(file_path)
    yield


@pytest.fixture
def recording_injection(mocker: MockerFixture, recording_file_override):
    if RecordStorage.is_replaying_mode() or RecordStorage.is_recording_mode():
        original_fun = FlowExecutionContext._invoke_tool_with_timer
        mocker.patch(
            "promptflow._core.flow_execution_context.FlowExecutionContext._invoke_tool_with_timer",
            mock_origin(original_fun),
        )
    yield
