import multiprocessing
from asyncio import Queue
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
from unittest.mock import patch

import pytest
from pytest_mock import MockerFixture
from sdk_cli_test.recording_utilities import RecordStorage, mock_tool, recording_array_extend, recording_array_reset

from promptflow.executor._line_execution_process_pool import _process_wrapper

PROMPTFLOW_ROOT = Path(__file__) / "../../.."
RECORDINGS_TEST_CONFIGS_ROOT = Path(PROMPTFLOW_ROOT / "tests/test_configs/node_recordings").resolve()


@contextmanager
def apply_recording_injection_if_enabled():
    # multiprocessing.get_context("spawn").Process = MockSpawnProcess
    # multiprocessing.Process = MockSpawnProcess

    patches = []
    if RecordStorage.is_replaying_mode() or RecordStorage.is_recording_mode():
        file_path = RECORDINGS_TEST_CONFIGS_ROOT / "node_cache.shelve"
        RecordStorage.get_instance(file_path)

        from promptflow._core.tool import tool as original_tool

        mocked_tool = mock_tool(original_tool)
        patch_targets = ["promptflow._core.tool.tool", "promptflow._internal.tool", "promptflow.tool"]

        for target in patch_targets:
            patcher = patch(target, mocked_tool)
            patches.append(patcher)
            patcher.start()

    try:
        yield
    finally:
        for patcher in patches:
            patcher.stop()


def recording_injection_decorator(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        multiprocessing.get_context("spawn").Process = MockSpawnProcess
        multiprocessing.Process = MockSpawnProcess
        with apply_recording_injection_if_enabled():
            return func(*args, **kwargs)

    return wrapper


def recording_injection_decorator_compatible_with_spawn(mock_class):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            original_process_class = multiprocessing.get_context("spawn").Process
            multiprocessing.get_context("spawn").Process = mock_class
            multiprocessing.Process = mock_class
            try:
                with apply_recording_injection_if_enabled():
                    return func(*args, **kwargs)
            finally:
                multiprocessing.get_context("spawn").Process = original_process_class
                multiprocessing.Process = original_process_class

        return wrapper

    return decorator


SpawnProcess = multiprocessing.get_context("spawn").Process


class MockSpawnProcess(SpawnProcess):
    def __init__(self, group=None, target=None, *args, **kwargs):
        if target == _process_wrapper:
            target = _mock_process_wrapper
        super().__init__(group, target, *args, **kwargs)


@pytest.fixture
def recording_file_override(request: pytest.FixtureRequest, mocker: MockerFixture):
    if RecordStorage.is_replaying_mode() or RecordStorage.is_recording_mode():
        file_path = RECORDINGS_TEST_CONFIGS_ROOT / "executor_node_cache.shelve"
        RecordStorage.get_instance(file_path)
    yield


@pytest.fixture
@recording_injection_decorator
def recording_injection():

    try:
        yield (RecordStorage.is_replaying_mode() or RecordStorage.is_recording_mode(), recording_array_extend)
    finally:
        if RecordStorage.is_replaying_mode() or RecordStorage.is_recording_mode():
            RecordStorage.get_instance().delete_lock_file()
        recording_array_reset()


@recording_injection_decorator_compatible_with_spawn(MockSpawnProcess)
def _mock_process_wrapper(
    executor_creation_func,
    input_queue: Queue,
    output_queue: Queue,
    log_context_initialization_func,
    operation_contexts_dict: dict,
):
    _process_wrapper(
        executor_creation_func, input_queue, output_queue, log_context_initialization_func, operation_contexts_dict
    )
