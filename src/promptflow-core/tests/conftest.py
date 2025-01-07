import json
import multiprocessing
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture

from promptflow._utils.flow_utils import resolve_flow_path
from promptflow.core._connection_provider._connection_provider import ConnectionProvider
from promptflow.core._connection_provider._dict_connection_provider import DictConnectionProvider
from promptflow.core._serving.app import create_app as create_serving_app
from promptflow.executor._line_execution_process_pool import _process_wrapper
from promptflow.executor._process_manager import create_spawned_fork_process_manager
from promptflow.recording.local import recording_array_reset
from promptflow.recording.record_mode import is_in_ci_pipeline, is_live, is_record, is_replay
from promptflow.tracing._integrations._openai_injector import inject_openai_api

PROMPTFLOW_ROOT = Path(__file__).parent.parent.parent / "promptflow"
TEST_CONFIG_ROOT = Path(__file__).parent.parent.parent / "promptflow" / "tests" / "test_configs"
FLOW_ROOT = TEST_CONFIG_ROOT / "flows"
EAGER_FLOW_ROOT = TEST_CONFIG_ROOT / "eager_flows"
CONNECTION_FILE = PROMPTFLOW_ROOT / "connections.json"
RECORDINGS_TEST_CONFIGS_ROOT = Path(PROMPTFLOW_ROOT / "../promptflow-recording/recordings/local").resolve()
COUNTER_FILE = (Path(__file__) / "../count.json").resolve()


def get_flow_folder(folder_name, root: str = FLOW_ROOT) -> Path:
    flow_folder_path = Path(root) / folder_name
    return flow_folder_path


def get_yaml_file(folder_name, root: str = FLOW_ROOT, file_name: str = None) -> Path:
    if file_name is None:
        flow_path, flow_file = resolve_flow_path(get_flow_folder(folder_name, root), check_flow_exist=False)
        yaml_file = flow_path / flow_file
    else:
        yaml_file = get_flow_folder(folder_name, root) / file_name

    return yaml_file


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
            from promptflow.recording.local import RecordStorage

            RecordStorage.get_instance().delete_lock_file()
        if is_live():
            from promptflow.recording.local import Counter

            Counter.set_file(COUNTER_FILE)
            Counter.delete_count_lock_file()
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
        from promptflow.recording.local import (
            RecordStorage,
            inject_async_with_recording,
            inject_sync_with_recording,
            mock_tool,
        )
        from promptflow.recording.record_mode import check_pydantic_v2

        check_pydantic_v2()
        file_path = RECORDINGS_TEST_CONFIGS_ROOT / "core_node_cache.shelve"
        RecordStorage.get_instance(file_path)

        from promptflow._core.tool import tool as original_tool

        mocked_tool = mock_tool(original_tool)
        patch_targets = {
            "promptflow._core.tool.tool": mocked_tool,
            # "promptflow.tool": mocked_tool,
            "promptflow.core.tool": mocked_tool,
            "promptflow.tracing._integrations._openai_injector.inject_sync": inject_sync_with_recording,
            "promptflow.tracing._integrations._openai_injector.inject_async": inject_async_with_recording,
        }
        start_patches(patch_targets)

    if is_live() and is_in_ci_pipeline():
        from promptflow.recording.local import Counter, inject_async_with_recording, inject_sync_with_recording

        Counter.set_file(COUNTER_FILE)
        patch_targets = {
            "promptflow.tracing._integrations._openai_injector.inject_sync": inject_sync_with_recording,
            "promptflow.tracing._integrations._openai_injector.inject_async": inject_async_with_recording,
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


@pytest.fixture
def setup_connection_provider():
    if not ConnectionProvider._instance:
        connection_dict = json.loads(open(CONNECTION_FILE, "r").read())
        ConnectionProvider._instance = DictConnectionProvider(connection_dict)
    # patch get instance as executor run with sub-process and lost class instance
    with patch(
        "promptflow.connections.ConnectionProvider.get_instance",
        return_value=ConnectionProvider._instance,
    ):
        yield


@pytest.fixture
def dev_connections() -> dict:
    with open(CONNECTION_FILE, "r") as f:
        return json.load(f)


# ==================== serving fixtures ====================


@pytest.fixture
def serving_inject_dict_provider(setup_connection_provider):
    with patch(
        "promptflow.core._serving.flow_invoker.ConnectionProvider.init_from_provider_config",
        return_value=ConnectionProvider._instance,
    ):
        yield


def create_client_by_model(
    model_name: str,
    mocker: MockerFixture,
    connections: dict = {},
    extension_type=None,
    environment_variables={},
    model_root=FLOW_ROOT,
    init=None,
):
    model_path = (Path(model_root) / model_name).resolve().absolute().as_posix()
    mocker.patch.dict(os.environ, {"PROMPTFLOW_PROJECT_PATH": model_path})
    if connections:
        mocker.patch.dict(os.environ, connections)
    if extension_type and extension_type == "azureml":
        environment_variables["API_TYPE"] = "${azure_open_ai_connection.api_type}"
    app = create_serving_app(environment_variables=environment_variables, extension_type=extension_type, init=init)
    app.config.update(
        {
            "TESTING": True,
        }
    )
    return app.test_client()


@pytest.fixture
def flow_serving_client(mocker: MockerFixture):
    model_path = (Path(FLOW_ROOT) / "basic-with-connection").resolve().absolute().as_posix()
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


@pytest.fixture
def stream_output(mocker: MockerFixture):
    return create_client_by_model("stream_output", mocker, model_root=EAGER_FLOW_ROOT)


@pytest.fixture
def multiple_stream_outputs(mocker: MockerFixture):
    return create_client_by_model("multiple_stream_outputs", mocker, model_root=EAGER_FLOW_ROOT)


@pytest.fixture
def eager_flow_evc(mocker: MockerFixture):
    return create_client_by_model("environment_variables_connection", mocker, model_root=EAGER_FLOW_ROOT)


@pytest.fixture
def eager_flow_evc_override(mocker: MockerFixture):
    return create_client_by_model(
        "environment_variables_connection",
        mocker,
        model_root=EAGER_FLOW_ROOT,
        environment_variables={"TEST": "${azure_open_ai_connection.api_base}"},
    )


@pytest.fixture
def eager_flow_evc_override_not_exist(mocker: MockerFixture):
    return create_client_by_model(
        "environment_variables",
        mocker,
        model_root=EAGER_FLOW_ROOT,
        environment_variables={"TEST": "${azure_open_ai_connection.api_type}"},
    )


@pytest.fixture
def eager_flow_evc_connection_not_exist(mocker: MockerFixture):
    return create_client_by_model(
        "evc_connection_not_exist",
        mocker,
        model_root=EAGER_FLOW_ROOT,
        environment_variables={"TEST": "VALUE"},
    )


@pytest.fixture
def callable_class(mocker: MockerFixture):
    return create_client_by_model(
        "basic_callable_class", mocker, model_root=EAGER_FLOW_ROOT, init={"obj_input": "input1"}
    )


# ==================== FastAPI serving fixtures ====================


def create_fastapi_app(**kwargs):
    return create_serving_app(engine="fastapi", **kwargs)


@pytest.fixture
def fastapi_flow_serving_client(mocker: MockerFixture):
    # model_path = (Path(MODEL_ROOT) / "basic-with-connection").resolve().absolute().as_posix()
    # mocker.patch.dict(os.environ, {"PROMPTFLOW_PROJECT_PATH": model_path})
    # mocker.patch.dict(os.environ, {"USER_AGENT": "test-user-agent"})
    # app = create_fastapi_app(environment_variables={"API_TYPE": "${azure_open_ai_connection.api_type}"})
    return fastapi_create_client_by_model(
        "basic-with-connection",
        mocker,
        mock_envs={"USER_AGENT": "test-user-agent"},
        environment_variables={"API_TYPE": "${azure_open_ai_connection.api_type}"},
    )
    # return TestClient(app)


def fastapi_create_client_by_model(
    model_name: str,
    mocker: MockerFixture,
    mock_envs: dict = {},
    extension_type=None,
    environment_variables={},
    model_root=FLOW_ROOT,
    init=None,
):
    model_path = (Path(model_root) / model_name).resolve().absolute().as_posix()
    mocker.patch.dict(os.environ, {"PROMPTFLOW_PROJECT_PATH": model_path})
    if mock_envs:
        mocker.patch.dict(os.environ, mock_envs)
    if extension_type and extension_type == "azureml":
        environment_variables["API_TYPE"] = "${azure_open_ai_connection.api_type}"
    app = create_fastapi_app(environment_variables=environment_variables, extension_type=extension_type, init=init)
    return TestClient(app)


@pytest.fixture
def fastapi_simple_eager_flow(mocker: MockerFixture):
    return fastapi_create_client_by_model("simple_with_dict_output", mocker, model_root=EAGER_FLOW_ROOT)


@pytest.fixture
def fastapi_simple_eager_flow_primitive_output(mocker: MockerFixture):
    return fastapi_create_client_by_model("primitive_output", mocker, model_root=EAGER_FLOW_ROOT)


@pytest.fixture
def fastapi_simple_eager_flow_dataclass_output(mocker: MockerFixture):
    return fastapi_create_client_by_model("flow_with_dataclass_output", mocker, model_root=EAGER_FLOW_ROOT)


@pytest.fixture
def fastapi_non_json_serializable_output(mocker: MockerFixture):
    return fastapi_create_client_by_model("non_json_serializable_output", mocker, model_root=EAGER_FLOW_ROOT)


@pytest.fixture
def fastapi_stream_output(mocker: MockerFixture):
    return fastapi_create_client_by_model("stream_output", mocker, model_root=EAGER_FLOW_ROOT)


@pytest.fixture
def fastapi_multiple_stream_outputs(mocker: MockerFixture):
    return fastapi_create_client_by_model("multiple_stream_outputs", mocker, model_root=EAGER_FLOW_ROOT)


@pytest.fixture
def fastapi_eager_flow_evc(mocker: MockerFixture):
    return fastapi_create_client_by_model("environment_variables_connection", mocker, model_root=EAGER_FLOW_ROOT)


@pytest.fixture
def fastapi_eager_flow_evc_override(mocker: MockerFixture):
    return fastapi_create_client_by_model(
        "environment_variables_connection",
        mocker,
        model_root=EAGER_FLOW_ROOT,
        environment_variables={"TEST": "${azure_open_ai_connection.api_base}"},
    )


@pytest.fixture
def fastapi_eager_flow_evc_override_not_exist(mocker: MockerFixture):
    return fastapi_create_client_by_model(
        "environment_variables",
        mocker,
        model_root=EAGER_FLOW_ROOT,
        environment_variables={"TEST": "${azure_open_ai_connection.api_type}"},
    )


@pytest.fixture
def fastapi_eager_flow_evc_connection_not_exist(mocker: MockerFixture):
    return fastapi_create_client_by_model(
        "evc_connection_not_exist",
        mocker,
        model_root=EAGER_FLOW_ROOT,
        environment_variables={"TEST": "VALUE"},
    )


@pytest.fixture
def fastapi_callable_class(mocker: MockerFixture):
    return fastapi_create_client_by_model(
        "basic_callable_class", mocker, model_root=EAGER_FLOW_ROOT, init={"obj_input": "input1"}
    )
