import contextlib
import contextvars
import json
import multiprocessing
import os
import traceback
from multiprocessing import Queue, get_context
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture

from promptflow._constants import PROMPTFLOW_CONNECTIONS
from promptflow.core._connection_provider._connection_provider import ConnectionProvider
from promptflow.core._connection_provider._dict_connection_provider import DictConnectionProvider
from promptflow.core._serving.app import create_app as create_serving_app
from promptflow.executor._line_execution_process_pool import _process_wrapper
from promptflow.executor._process_manager import create_spawned_fork_process_manager
from promptflow.recording.local import recording_array_reset
from promptflow.recording.record_mode import is_in_ci_pipeline, is_live, is_record, is_replay
from promptflow.tracing._integrations._openai_injector import inject_openai_api

from .utils import FLEX_FLOW_ROOT, FLOW_ROOT

PROMPTFLOW_ROOT = Path(__file__).parent.parent.parent / "promptflow"
TEST_CONFIG_ROOT = Path(__file__).parent.parent.parent / "promptflow" / "tests" / "test_configs"
CONNECTION_FILE = PROMPTFLOW_ROOT / "connections.json"
RECORDINGS_TEST_CONFIGS_ROOT = Path(PROMPTFLOW_ROOT / "../promptflow-recording/recordings/local").resolve()
COUNTER_FILE = (Path(__file__) / "../count.json").resolve()


def _run_in_subprocess(error_queue: Queue, func, args, kwargs):
    try:
        func(*args, **kwargs)
    except BaseException as e:
        error_queue.put((repr(e), traceback.format_exc()))


def _run_in_subprocess_with_recording(*args, **kwargs):
    setup_recording_injection_if_enabled()
    _run_in_subprocess(*args, **kwargs)


def execute_function_in_subprocess(func, *args, **kwargs):
    """
    Execute a function in a new process and return any exception that occurs.
    Replace pickle with dill for better serialization capabilities.
    """
    ctx = get_context("spawn")
    error_queue = ctx.Queue()
    process = ctx.Process(target=_run_in_subprocess_with_recording, args=(error_queue, func, args, kwargs))
    process.start()
    process.join()  # Wait for the process to finish

    if not error_queue.empty():
        err, stacktrace_str = error_queue.get()
        raise Exception(f"An error occurred in the subprocess: {err}\nStacktrace:\n{stacktrace_str}")
    assert process.exitcode == 0, f"Subprocess exited with code {process.exitcode}"


SpawnProcess = multiprocessing.Process
if "spawn" in multiprocessing.get_all_start_methods():
    SpawnProcess = multiprocessing.get_context("spawn").Process


ForkServerProcess = multiprocessing.Process
if "forkserver" in multiprocessing.get_all_start_methods():
    ForkServerProcess = multiprocessing.get_context("forkserver").Process


# Define context variables with default values
current_process_wrapper_var = contextvars.ContextVar("current_process_wrapper", default=_process_wrapper)
current_process_manager_var = contextvars.ContextVar(
    "current_process_manager", default=create_spawned_fork_process_manager
)


class BaseMockProcess:
    # Base class for the mock process; This class is mainly used as the placeholder for the target mocking logic
    def modify_target(self, target):
        # Method to modify the target of the mock process
        # This shall be the place to hold the target mocking logic
        if target == _process_wrapper:
            return current_process_wrapper_var.get()
        if target == create_spawned_fork_process_manager:
            return current_process_manager_var.get()
        return target


class MockSpawnProcess(SpawnProcess, BaseMockProcess):
    def __init__(self, group=None, target=None, *args, **kwargs):
        modified_target = self.modify_target(target)
        super().__init__(group, modified_target, *args, **kwargs)


class MockForkServerProcess(ForkServerProcess, BaseMockProcess):
    def __init__(self, group=None, target=None, *args, **kwargs):
        modified_target = self.modify_target(target)
        super().__init__(group, modified_target, *args, **kwargs)


def _default_mock_process_wrapper(*args, **kwargs):
    # Default mock implementation of _process_wrapper in recording mode
    setup_recording_injection_if_enabled()
    _process_wrapper(*args, **kwargs)


def _default_mock_create_spawned_fork_process_manager(*args, **kwargs):
    # Default mock implementation of create_spawned_fork_process_manager in recording mode
    setup_recording_injection_if_enabled()
    create_spawned_fork_process_manager(*args, **kwargs)


def override_process_class(process_class_dict: dict):
    original_process_class = {}
    for start_method, MockProcessClass in process_class_dict.items():
        if start_method in multiprocessing.get_all_start_methods():
            original_process_class[start_method] = multiprocessing.get_context(start_method).Process
            multiprocessing.get_context(start_method).Process = MockProcessClass
            if start_method == multiprocessing.get_start_method():
                multiprocessing.Process = MockProcessClass
    return original_process_class


@contextlib.contextmanager
def override_process_pool_targets(process_wrapper=None, process_manager=None):
    """
    Context manager to override the process pool targets for the current context

    """
    original_process_wrapper = current_process_wrapper_var.get()
    original_process_manager = current_process_manager_var.get()

    if process_wrapper is not None:
        current_process_wrapper_var.set(process_wrapper)
    if process_manager is not None:
        current_process_manager_var.set(process_manager)
    original_process_class = override_process_class({"spawn": MockSpawnProcess, "forkserver": MockForkServerProcess})

    try:
        yield
    finally:
        # Revert back to the original states
        current_process_wrapper_var.set(original_process_wrapper)
        current_process_manager_var.set(original_process_manager)
        override_process_class(original_process_class)


@pytest.fixture
def process_override():
    # This fixture is used to override the Process class to ensure the recording mode works

    # Step I: set process pool targets placeholder with customized targets
    current_process_wrapper_var.set(_default_mock_process_wrapper)
    current_process_manager_var.set(_default_mock_create_spawned_fork_process_manager)

    # Step II: override the process pool class
    process_class_dict = {"spawn": MockSpawnProcess, "forkserver": MockForkServerProcess}
    original_process_class = override_process_class(process_class_dict)

    try:
        yield
    finally:
        for start_method, MockProcessClass in process_class_dict.items():
            if start_method in multiprocessing.get_all_start_methods():
                multiprocessing.get_context(start_method).Process = original_process_class[start_method]
                if start_method == multiprocessing.get_start_method():
                    multiprocessing.Process = original_process_class[start_method]


@pytest.fixture
def recording_injection():
    # This fixture is used to main entry point to inject recording mode into the test
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
        file_path = RECORDINGS_TEST_CONFIGS_ROOT / "node_cache.shelve"
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


@pytest.fixture
def use_secrets_config_file(mocker: MockerFixture):
    mocker.patch.dict(os.environ, {PROMPTFLOW_CONNECTIONS: str(CONNECTION_FILE)})


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
    return create_client_by_model("simple_with_dict_output", mocker, model_root=FLEX_FLOW_ROOT)


@pytest.fixture
def simple_eager_flow_primitive_output(mocker: MockerFixture):
    return create_client_by_model("primitive_output", mocker, model_root=FLEX_FLOW_ROOT)


@pytest.fixture
def simple_eager_flow_dataclass_output(mocker: MockerFixture):
    return create_client_by_model("flow_with_dataclass_output", mocker, model_root=FLEX_FLOW_ROOT)


@pytest.fixture
def non_json_serializable_output(mocker: MockerFixture):
    return create_client_by_model("non_json_serializable_output", mocker, model_root=FLEX_FLOW_ROOT)


@pytest.fixture
def stream_output(mocker: MockerFixture):
    return create_client_by_model("stream_output", mocker, model_root=FLEX_FLOW_ROOT)


@pytest.fixture
def multiple_stream_outputs(mocker: MockerFixture):
    return create_client_by_model("multiple_stream_outputs", mocker, model_root=FLEX_FLOW_ROOT)


@pytest.fixture
def eager_flow_evc(mocker: MockerFixture):
    return create_client_by_model("environment_variables_connection", mocker, model_root=FLEX_FLOW_ROOT)


@pytest.fixture
def eager_flow_evc_override(mocker: MockerFixture):
    return create_client_by_model(
        "environment_variables_connection",
        mocker,
        model_root=FLEX_FLOW_ROOT,
        environment_variables={"TEST": "${azure_open_ai_connection.api_base}"},
    )


@pytest.fixture
def eager_flow_evc_override_not_exist(mocker: MockerFixture):
    return create_client_by_model(
        "environment_variables",
        mocker,
        model_root=FLEX_FLOW_ROOT,
        environment_variables={"TEST": "${azure_open_ai_connection.api_type}"},
    )


@pytest.fixture
def eager_flow_evc_connection_not_exist(mocker: MockerFixture):
    return create_client_by_model(
        "evc_connection_not_exist",
        mocker,
        model_root=FLEX_FLOW_ROOT,
        environment_variables={"TEST": "VALUE"},
    )


@pytest.fixture
def callable_class(mocker: MockerFixture):
    return create_client_by_model(
        "basic_callable_class", mocker, model_root=FLEX_FLOW_ROOT, init={"obj_input": "input1"}
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
    return fastapi_create_client_by_model("simple_with_dict_output", mocker, model_root=FLEX_FLOW_ROOT)


@pytest.fixture
def fastapi_simple_eager_flow_primitive_output(mocker: MockerFixture):
    return fastapi_create_client_by_model("primitive_output", mocker, model_root=FLEX_FLOW_ROOT)


@pytest.fixture
def fastapi_simple_eager_flow_dataclass_output(mocker: MockerFixture):
    return fastapi_create_client_by_model("flow_with_dataclass_output", mocker, model_root=FLEX_FLOW_ROOT)


@pytest.fixture
def fastapi_non_json_serializable_output(mocker: MockerFixture):
    return fastapi_create_client_by_model("non_json_serializable_output", mocker, model_root=FLEX_FLOW_ROOT)


@pytest.fixture
def fastapi_stream_output(mocker: MockerFixture):
    return fastapi_create_client_by_model("stream_output", mocker, model_root=FLEX_FLOW_ROOT)


@pytest.fixture
def fastapi_multiple_stream_outputs(mocker: MockerFixture):
    return fastapi_create_client_by_model("multiple_stream_outputs", mocker, model_root=FLEX_FLOW_ROOT)


@pytest.fixture
def fastapi_eager_flow_evc(mocker: MockerFixture):
    return fastapi_create_client_by_model("environment_variables_connection", mocker, model_root=FLEX_FLOW_ROOT)


@pytest.fixture
def fastapi_eager_flow_evc_override(mocker: MockerFixture):
    return fastapi_create_client_by_model(
        "environment_variables_connection",
        mocker,
        model_root=FLEX_FLOW_ROOT,
        environment_variables={"TEST": "${azure_open_ai_connection.api_base}"},
    )


@pytest.fixture
def fastapi_eager_flow_evc_override_not_exist(mocker: MockerFixture):
    return fastapi_create_client_by_model(
        "environment_variables",
        mocker,
        model_root=FLEX_FLOW_ROOT,
        environment_variables={"TEST": "${azure_open_ai_connection.api_type}"},
    )


@pytest.fixture
def fastapi_eager_flow_evc_connection_not_exist(mocker: MockerFixture):
    return fastapi_create_client_by_model(
        "evc_connection_not_exist",
        mocker,
        model_root=FLEX_FLOW_ROOT,
        environment_variables={"TEST": "VALUE"},
    )


@pytest.fixture
def fastapi_callable_class(mocker: MockerFixture):
    return fastapi_create_client_by_model(
        "basic_callable_class", mocker, model_root=FLEX_FLOW_ROOT, init={"obj_input": "input1"}
    )
