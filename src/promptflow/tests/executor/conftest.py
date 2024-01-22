import multiprocessing
from asyncio import Queue
from pathlib import Path
from unittest.mock import patch

import pytest
from sdk_cli_test.recording_utilities import RecordStorage, mock_tool, recording_array_extend, recording_array_reset

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
    override_recording_file()
    if RecordStorage.is_replaying_mode() or RecordStorage.is_recording_mode():
        from promptflow._core.tool import tool as original_tool

        mocked_tool = mock_tool(original_tool)
        patch_targets = ["promptflow._core.tool.tool", "promptflow._internal.tool", "promptflow.tool"]

        for target in patch_targets:
            patcher = patch(target, mocked_tool)
            patches.append(patcher)
            patcher.start()
    return patches


def _default_mock_process_wrapper(
    executor_creation_func,
    input_queue: Queue,
    output_queue: Queue,
    log_context_initialization_func,
    operation_contexts_dict: dict,
):
    setup_recording()
    _process_wrapper(
        executor_creation_func, input_queue, output_queue, log_context_initialization_func, operation_contexts_dict
    )


def _default_mock_create_spawned_fork_process_manager(
    log_context_initialization_func,
    current_operation_context,
    input_queues,
    output_queues,
    control_signal_queue,
    flow_file,
    connections,
    working_dir,
    raise_ex,
    process_info,
    process_target_func,
):
    setup_recording()
    create_spawned_fork_process_manager(
        log_context_initialization_func,
        current_operation_context,
        input_queues,
        output_queues,
        control_signal_queue,
        flow_file,
        connections,
        working_dir,
        raise_ex,
        process_info,
        process_target_func,
    )


# Placeholder for the current strategy
current_process_wrapper = _default_mock_process_wrapper
current_process_manager = _default_mock_create_spawned_fork_process_manager


def get_current_process_wrapper():
    return current_process_wrapper


def set_current_process_wrapper(strategy_func):
    global current_process_wrapper
    current_process_wrapper = strategy_func


def get_current_process_manager():
    return current_process_manager


def set_current_process_manager(strategy_func):
    global current_process_manager
    current_process_manager = strategy_func


SpawnProcess = multiprocessing.Process
if "spawn" in multiprocessing.get_all_start_methods():
    SpawnProcess = multiprocessing.get_context("spawn").Process

ForkServerProcess = multiprocessing.Process
if "forkserver" in multiprocessing.get_all_start_methods():
    ForkServerProcess = multiprocessing.get_context("forkserver").Process


class BaseMockProcess:
    def modify_target(self, target):
        if target == _process_wrapper:
            return get_current_process_wrapper()
        if target == create_spawned_fork_process_manager:
            return get_current_process_manager()
        return target


class MockSpawnProcess(SpawnProcess, BaseMockProcess):
    def __init__(self, group=None, target=None, *args, **kwargs):
        modified_target = self.modify_target(target)
        super().__init__(group, modified_target, *args, **kwargs)


class MockForkServerProcess(ForkServerProcess, BaseMockProcess):
    def __init__(self, group=None, target=None, *args, **kwargs):
        modified_target = self.modify_target(target)
        super().__init__(group, modified_target, *args, **kwargs)


@pytest.fixture
def recording_file_override():
    override_recording_file()
    yield


def override_recording_file():
    if RecordStorage.is_replaying_mode() or RecordStorage.is_recording_mode():
        file_path = RECORDINGS_TEST_CONFIGS_ROOT / "executor_node_cache.shelve"
        RecordStorage.get_instance(file_path)


@pytest.fixture
def process_override():
    # This fixture is used to override the Process class to ensure the recording mode works
    start_methods_mocks = {"spawn": MockSpawnProcess, "forkserver": MockForkServerProcess}
    original_process_class = {}
    for start_method, MockProcessClass in start_methods_mocks.items():
        if start_method in multiprocessing.get_all_start_methods():
            original_process_class[start_method] = multiprocessing.get_context(start_method).Process
            multiprocessing.get_context(start_method).Process = MockProcessClass
            if start_method == multiprocessing.get_start_method():
                multiprocessing.Process = MockProcessClass

    try:
        yield
    finally:
        for start_method, MockProcessClass in start_methods_mocks.items():
            if start_method in multiprocessing.get_all_start_methods():
                multiprocessing.get_context(start_method).Process = original_process_class[start_method]
                if start_method == multiprocessing.get_start_method():
                    multiprocessing.Process = original_process_class[start_method]


@pytest.fixture
def recording_injection(recording_setup, process_override):
    # This fixture is used to main entry point to inject recording mode into the test
    try:
        yield (RecordStorage.is_replaying_mode() or RecordStorage.is_recording_mode(), recording_array_extend)
    finally:
        if RecordStorage.is_replaying_mode() or RecordStorage.is_recording_mode():
            RecordStorage.get_instance().delete_lock_file()
        recording_array_reset()
