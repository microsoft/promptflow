import multiprocessing
import os
from pathlib import Path

import pytest
from executor.process_utils import (
    MockForkServerProcess,
    MockSpawnProcess,
    current_process_manager_var,
    current_process_wrapper_var,
    override_process_class,
)
from fastapi.testclient import TestClient

from promptflow.executor._line_execution_process_pool import _process_wrapper
from promptflow.executor._process_manager import create_spawned_fork_process_manager
from promptflow.executor._service.app import app
from promptflow.tracing._integrations._openai_injector import inject_openai_api

from .record_utils import setup_recording

try:
    from promptflow.recording.local import recording_array_reset
    from promptflow.recording.record_mode import is_live, is_record, is_recording_enabled, is_replay
except ImportError:
    # Run test in empty mode if promptflow-recording is not installed
    def recording_array_reset():
        pass

    def is_live():
        return False

    def is_record():
        return False

    def is_recording_enabled():
        return False

    def is_replay():
        return False


# Enable tracing for testing
os.environ["PF_DISABLE_TRACING"] = "false"

PROMPTFLOW_ROOT = Path(__file__) / "../../.."


def pytest_configure(config):
    # Register an additional marker
    pytest.is_live = is_live()
    pytest.is_record = is_record()
    pytest.is_replay = is_replay()
    pytest.is_recording_enabled = is_recording_enabled()


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
def recording_injection(recording_setup, process_override):
    # This fixture is used to main entry point to inject recording mode into the test
    try:
        yield
    finally:
        if pytest.is_replay or pytest.is_record:
            from promptflow.recording.local import RecordStorage

            RecordStorage.get_instance().delete_lock_file()
        if pytest.is_live:
            from promptflow.recording.local import delete_count_lock_file

            delete_count_lock_file()
        recording_array_reset()


@pytest.fixture(autouse=True, scope="session")
def inject_api_executor():
    """Inject OpenAI API during test session when recording not enabled
    AOAI call in promptflow should involve trace logging and header injection. Inject
    function to API call in test scenario."""
    if not pytest.is_recording_enabled:
        inject_openai_api()


@pytest.fixture(autouse=True, scope="session")
def executor_client():
    """Executor client for testing."""
    # Set raise_server_exceptions to False to avoid raising exceptions
    # from the server and return them as error response.
    yield TestClient(app, raise_server_exceptions=False)
