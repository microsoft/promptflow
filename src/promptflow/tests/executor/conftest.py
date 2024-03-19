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
from executor.record_utils import setup_patching, setup_recording
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

PROMPTFLOW_ROOT = Path(__file__) / "../../.."


@pytest.fixture
def recording_setup():
    patches = setup_recording()
    try:
        yield
    finally:
        for patcher in patches:
            patcher.stop()


def _custom_mock_process_wrapper(*args, **kwargs):
    patch_dict = kwargs.pop("patch_dict", None)
    process_target = kwargs.pop("process_target", None)
    if patch_dict is not None:
        # Mock implementation with custom patch.
        setup_patching(patch_dict)
    else:
        # Mock implementation process in recording mode.
        setup_recording()
    process_target(*args, **kwargs)


def process_class_override_setup():
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


def setup_custom_process_target(patch_dict=None):
    current_process_wrapper_var.set(
        functools.partial(_custom_mock_process_wrapper, process_target=_process_wrapper, patch_dict=patch_dict)
    )
    current_process_manager_var.set(
        functools.partial(
            _custom_mock_process_wrapper, process_target=create_spawned_fork_process_manager, patch_dict=patch_dict
        )
    )


def process_override(patch_dict=None):
    # Step I: set process pool targets placeholder with customized targets
    setup_custom_process_target(patch_dict)
    # Step II: override the process pool class
    yield from process_class_override_setup()


@pytest.fixture
def recording_injection(recording_setup):
    yield from process_override()
    # This fixture is used to main entry point to inject recording mode into the test
    try:
        yield (is_replay() or is_record(), recording_array_extend)
    finally:
        if is_replay() or is_record():
            RecordStorage.get_instance().delete_lock_file()
        if is_live():
            delete_count_lock_file()
        recording_array_reset()


@pytest.fixture
def configure_process_with_custom_patch(patch_dict):
    yield from process_override(patch_dict)


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
