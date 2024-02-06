import multiprocessing
from pathlib import Path
from unittest.mock import patch

import pytest
from executor.process_utils import (
    MockForkServerProcess,
    MockSpawnProcess,
    current_process_manager_var,
    current_process_wrapper_var,
    override_process_class,
)
from sdk_cli_test.recording_utilities import (
    RecordStorage,
    delete_count_lock_file,
    inject_async_with_recording,
    inject_sync_with_recording,
    is_live,
    is_record,
    is_replay,
    mock_tool,
    recording_array_extend,
    recording_array_reset,
)
from sdk_cli_test.recording_utilities.record_storage import is_recording_enabled

from promptflow._core.openai_injector import inject_openai_api
from promptflow.executor._line_execution_process_pool import _process_wrapper
from promptflow.executor._process_manager import create_spawned_fork_process_manager

PROMPTFLOW_ROOT = Path(__file__) / "../../.."
RECORDINGS_TEST_CONFIGS_ROOT = Path(PROMPTFLOW_ROOT / "tests/test_configs/node_recordings").resolve()


@pytest.fixture
def recording_setup():
    patches = setup_recording()
    try:
        yield
    finally:
        for patcher in patches:
            patcher.stop()


def setup_recording():
    patches = []

    def start_patches(patch_targets):
        for target, mock_func in patch_targets.items():
            patcher = patch(target, mock_func)
            patches.append(patcher)
            patcher.start()

    if is_replay() or is_record():
        file_path = RECORDINGS_TEST_CONFIGS_ROOT / "executor_node_cache.shelve"
        RecordStorage.get_instance(file_path)

        from promptflow._core.tool import tool as original_tool

        mocked_tool = mock_tool(original_tool)
        patch_targets = {
            "promptflow._core.tool.tool": mocked_tool,
            "promptflow._internal.tool": mocked_tool,
            "promptflow.tool": mocked_tool,
            "promptflow._core.openai_injector.inject_sync": inject_sync_with_recording,
            "promptflow._core.openai_injector.inject_async": inject_async_with_recording,
        }
        start_patches(patch_targets)
        inject_openai_api()

    if is_live():
        patch_targets = {
            "promptflow._core.openai_injector.inject_sync": inject_sync_with_recording,
            "promptflow._core.openai_injector.inject_async": inject_async_with_recording,
        }
        start_patches(patch_targets)
        inject_openai_api()

    return patches


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
