import functools
import multiprocessing
from pathlib import Path

import pytest
from executor.process_utils import (
    MockForkServerProcess,
    MockSpawnProcess,
    current_process_manager_var,
    current_process_wrapper_var,
    override_process_class,
)
from executor.record_utils import mocked_flow_executor_patch, setup_recording
from fastapi.testclient import TestClient
from sdk_cli_test.recording_utilities import (
    RecordStorage,
    delete_count_lock_file,
    is_live,
    is_record,
    is_replay,
    recording_array_extend,
    recording_array_reset,
)
from sdk_cli_test.recording_utilities.record_storage import is_recording_enabled

from promptflow.executor._line_execution_process_pool import _process_wrapper
from promptflow.executor._process_manager import create_spawned_fork_process_manager
from promptflow.executor._service.app import app
from promptflow.tracing._integrations._openai_injector import inject_openai_api

from .mock_functions import mock_flow_execution_context

PROMPTFLOW_ROOT = Path(__file__) / "../../.."


@pytest.fixture
def recording_setup():
    patches = setup_recording()
    try:
        yield
    finally:
        for patcher in patches:
            patcher.stop()


def _default_mock_process_wrapper(*args, **kwargs):
    # Default mock implementation of _process_wrapper in recording mode
    setup_recording()
    _process_wrapper(*args, **kwargs)


def _default_mock_create_spawned_fork_process_manager(*args, **kwargs):
    # Default mock implementation of create_spawned_fork_process_manager in recording mode
    setup_recording()
    create_spawned_fork_process_manager(*args, **kwargs)


def _common_mock_process_wrapper(*args, **kwargs):
    # Default mock implementation of _process_wrapper in recording mode
    patch_target_list = kwargs.pop("patch_target_list", None)
    mock_function_list = kwargs.pop("mock_function_list", None)
    mocked_flow_executor_patch(patch_target_list, mock_function_list)
    _process_wrapper(*args, **kwargs)


def _common_mock_create_spawned_fork_process_manager(*args, **kwargs):
    # Default mock implementation of create_spawned_fork_process_manager in recording mode
    patch_target_list = kwargs.pop("patch_target_list", None)
    mock_function_list = kwargs.pop("mock_function_list", None)
    mocked_flow_executor_patch(patch_target_list, mock_function_list)
    create_spawned_fork_process_manager(*args, **kwargs)


def process_override_setup():
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
def process_override():
    # This fixture is used to override the Process class to ensure the recording mode works

    # Step I: set process pool targets placeholder with customized targets
    current_process_wrapper_var.set(_default_mock_process_wrapper)
    current_process_manager_var.set(_default_mock_create_spawned_fork_process_manager)

    yield from process_override_setup()


def configure_process_override_with_custom_parameters(patch_target_list, mock_function_list):
    # This fixture is used to override the Process class to ensure the recording mode works

    # Step I: set process pool targets placeholder with customized targets
    current_process_wrapper_var.set(
        functools.partial(
            _common_mock_process_wrapper, patch_target_list=patch_target_list, mock_function_list=mock_function_list
        )
    )
    current_process_manager_var.set(
        functools.partial(
            _common_mock_create_spawned_fork_process_manager,
            patch_target_list=patch_target_list,
            mock_function_list=mock_function_list,
        )
    )

    yield from process_override_setup()


@pytest.fixture
def recording_injection(recording_setup, process_override):
    # This fixture is used as the main entry point to inject recording mode into the test
    return _inject_recording_mode(recording_setup, process_override)


@pytest.fixture
def configure_flow_execution_context_init_with_error():
    patch_target_list = ["promptflow._core.flow_execution_context.FlowExecutionContext.__init__"]
    mock_function_list = [mock_flow_execution_context]
    yield from configure_process_override_with_custom_parameters(patch_target_list, mock_function_list)


def _inject_recording_mode(setup_function, process_override_function):
    try:
        yield (is_replay() or is_record(), recording_array_extend)
    finally:
        if is_replay() or is_record():
            RecordStorage.get_instance().delete_lock_file()
        if is_live():
            delete_count_lock_file()
        recording_array_reset()


@pytest.fixture(autouse=True, scope="session")
def inject_api_executor():
    """Inject OpenAI API during test session when recording not enabled
    AOAI call in promptflow should involve trace logging and header injection. Inject
    function to API call in test scenario."""
    if not is_recording_enabled():
        inject_openai_api()


@pytest.fixture(autouse=True, scope="session")
def executor_client():
    """Executor client for testing."""
    # Set raise_server_exceptions to False to avoid raising exceptions
    # from the server and return them as error response.
    yield TestClient(app, raise_server_exceptions=False)
