import base64
import json
import multiprocessing
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from mock import mock
from pytest_mock import MockerFixture
from sqlalchemy import create_engine

from promptflow import PFClient
from promptflow._sdk._configuration import Configuration
from promptflow._sdk._constants import EXPERIMENT_CREATED_ON_INDEX_NAME, EXPERIMENT_TABLE_NAME, LOCAL_MGMT_DB_PATH
from promptflow._sdk._serving.app import create_app as create_serving_app
from promptflow._sdk.entities import AzureOpenAIConnection as AzureOpenAIConnectionEntity
from promptflow._sdk.entities._connection import CustomConnection, _Connection
from promptflow._utils.utils import is_in_ci_pipeline
from promptflow.executor._line_execution_process_pool import _process_wrapper
from promptflow.executor._process_manager import create_spawned_fork_process_manager
from promptflow.tracing._openai_injector import inject_openai_api

from .recording_utilities import (
    RecordStorage,
    check_pydantic_v2,
    delete_count_lock_file,
    inject_async_with_recording,
    inject_sync_with_recording,
    is_live,
    is_record,
    is_replay,
    mock_tool,
    recording_array_reset,
)

PROMOTFLOW_ROOT = Path(__file__) / "../../.."
RUNTIME_TEST_CONFIGS_ROOT = Path(PROMOTFLOW_ROOT / "tests/test_configs/runtime")
RECORDINGS_TEST_CONFIGS_ROOT = Path(PROMOTFLOW_ROOT / "tests/test_configs/node_recordings").resolve()
CONNECTION_FILE = (PROMOTFLOW_ROOT / "connections.json").resolve().absolute().as_posix()
MODEL_ROOT = Path(PROMOTFLOW_ROOT / "tests/test_configs/flows")
EAGER_FLOW_ROOT = Path(PROMOTFLOW_ROOT / "tests/test_configs/eager_flows")


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
def setup_experiment_table():
    with mock.patch("promptflow._sdk._configuration.Configuration.is_internal_features_enabled") as mock_func:
        mock_func.return_value = True
        # Call this session to initialize session maker, then add experiment table
        from promptflow._sdk._orm import Experiment, mgmt_db_session
        from promptflow._sdk._orm.session import create_index_if_not_exists, create_or_update_table

        mgmt_db_session()
        engine = create_engine(f"sqlite:///{str(LOCAL_MGMT_DB_PATH)}", future=True)
        if Configuration.get_instance().is_internal_features_enabled():
            create_or_update_table(engine, orm_class=Experiment, tablename=EXPERIMENT_TABLE_NAME)
            create_index_if_not_exists(engine, EXPERIMENT_CREATED_ON_INDEX_NAME, EXPERIMENT_TABLE_NAME, "created_on")


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
def flow_serving_client_with_encoded_connection(mocker: MockerFixture):
    from promptflow._core.connection_manager import ConnectionManager
    from promptflow._sdk._serving.utils import encode_dict

    connection_dict = json.loads(open(CONNECTION_FILE, "r").read())
    connection_manager = ConnectionManager(connection_dict)
    connections = {"PROMPTFLOW_ENCODED_CONNECTIONS": encode_dict(connection_manager.to_connections_dict())}
    return create_client_by_model("basic-with-connection", mocker, connections, extension_type="azureml")


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


def create_client_by_model(
    model_name: str,
    mocker: MockerFixture,
    connections: dict = {},
    extension_type=None,
    environment_variables={},
    model_root=MODEL_ROOT,
):
    model_path = (Path(model_root) / model_name).resolve().absolute().as_posix()
    mocker.patch.dict(os.environ, {"PROMPTFLOW_PROJECT_PATH": model_path})
    if connections:
        mocker.patch.dict(os.environ, connections)
    if extension_type and extension_type == "azureml":
        environment_variables["API_TYPE"] = "${azure_open_ai_connection.api_type}"
    app = create_serving_app(environment_variables=environment_variables, extension_type=extension_type)
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


@pytest.fixture
def serving_client_with_environment_variables(mocker: MockerFixture):
    return create_client_by_model(
        "flow_with_environment_variables",
        mocker,
        environment_variables={"env2": "runtime_env2", "env10": "aaaaa"},
    )


@pytest.fixture
def simple_eager_flow(mocker: MockerFixture):
    return create_client_by_model("simple_with_dict_output", mocker, model_root=EAGER_FLOW_ROOT)


@pytest.fixture
def simple_eager_flow_primitive_output(mocker: MockerFixture):
    return create_client_by_model("primitive_output", mocker, model_root=EAGER_FLOW_ROOT)


@pytest.fixture
def simple_eager_flow_dataclass_output(mocker: MockerFixture):
    return create_client_by_model("flow_with_dataclass_output", mocker, model_root=EAGER_FLOW_ROOT)


@pytest.fixture
def non_json_serializable_output(mocker: MockerFixture):
    return create_client_by_model("non_json_serializable_output", mocker, model_root=EAGER_FLOW_ROOT)


# ==================== Recording injection ====================
# To inject patches in subprocesses, add new mock method in setup_recording_injection_if_enabled
# in fork mode, this is automatically enabled.
# in spawn mode, we need to decalre recording in each process separately.

SpawnProcess = multiprocessing.get_context("spawn").Process


class MockSpawnProcess(SpawnProcess):
    def __init__(self, group=None, target=None, *args, **kwargs):
        if target == _process_wrapper:
            target = _mock_process_wrapper
        if target == create_spawned_fork_process_manager:
            target = _mock_create_spawned_fork_process_manager
        super().__init__(group, target, *args, **kwargs)


@pytest.fixture
def recording_injection(mocker: MockerFixture):
    original_process_class = multiprocessing.get_context("spawn").Process
    multiprocessing.get_context("spawn").Process = MockSpawnProcess
    if "spawn" == multiprocessing.get_start_method():
        multiprocessing.Process = MockSpawnProcess

    patches = setup_recording_injection_if_enabled()

    try:
        yield
    finally:
        if is_replay() or is_record():
            RecordStorage.get_instance().delete_lock_file()
        if is_live():
            delete_count_lock_file()
        recording_array_reset()

        multiprocessing.get_context("spawn").Process = original_process_class
        if "spawn" == multiprocessing.get_start_method():
            multiprocessing.Process = original_process_class

        for patcher in patches:
            patcher.stop()


def setup_recording_injection_if_enabled():
    patches = []

    def start_patches(patch_targets):
        for target, mock_func in patch_targets.items():
            patcher = patch(target, mock_func)
            patches.append(patcher)
            patcher.start()

    if is_replay() or is_record():
        check_pydantic_v2()
        file_path = RECORDINGS_TEST_CONFIGS_ROOT / "node_cache.shelve"
        RecordStorage.get_instance(file_path)

        from promptflow._core.tool import tool as original_tool

        mocked_tool = mock_tool(original_tool)
        patch_targets = {
            "promptflow._core.tool.tool": mocked_tool,
            "promptflow._internal.tool": mocked_tool,
            "promptflow.tool": mocked_tool,
            "promptflow.tracing._openai_injector.inject_sync": inject_sync_with_recording,
            "promptflow.tracing._openai_injector.inject_async": inject_async_with_recording,
        }
        start_patches(patch_targets)

    if is_live() and is_in_ci_pipeline():
        patch_targets = {
            "promptflow.tracing._openai_injector.inject_sync": inject_sync_with_recording,
            "promptflow.tracing._openai_injector.inject_async": inject_async_with_recording,
        }
        start_patches(patch_targets)

    inject_openai_api()
    return patches


def _mock_process_wrapper(*args, **kwargs):
    setup_recording_injection_if_enabled()
    return _process_wrapper(*args, **kwargs)


def _mock_create_spawned_fork_process_manager(*args, **kwargs):
    setup_recording_injection_if_enabled()
    return create_spawned_fork_process_manager(*args, **kwargs)
