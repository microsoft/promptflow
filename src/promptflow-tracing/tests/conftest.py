import json
import multiprocessing
from pathlib import Path
from unittest.mock import patch

import pytest
from pytest_mock import MockerFixture

from promptflow.tracing._integrations._openai_injector import inject_openai_api

try:
    from promptflow.recording.local import recording_array_reset
    from promptflow.recording.record_mode import is_in_ci_pipeline, is_live, is_record, is_replay
except ImportError:
    # Run test in empty mode if promptflow-recording is not installed
    def recording_array_reset():
        pass

    def is_in_ci_pipeline():
        return False

    def is_live():
        return False

    def is_record():
        return False

    def is_replay():
        return False


from .utils import _run_in_subprocess

RECORDINGS_TEST_CONFIGS_ROOT = Path(__file__).parent.parent.parent / "promptflow-recording/recordings/local"


def pytest_configure():
    pytest.is_live = is_live()
    pytest.is_record = is_record()
    pytest.is_replay = is_replay()
    pytest.is_in_ci_pipeline = is_in_ci_pipeline()


@pytest.fixture
def dev_connections() -> dict:
    with open(
        file=(Path(__file__).parent.parent / "connections.json").resolve().absolute().as_posix(),
        mode="r",
    ) as f:
        return json.load(f)


# ==================== Recording injection ====================
# To inject patches in subprocesses, add new mock method in setup_recording_injection_if_enabled
# in fork mode, this is automatically enabled.
# in spawn mode, we need to declare recording in each process separately.

SpawnProcess = multiprocessing.get_context("spawn").Process


class MockSpawnProcess(SpawnProcess):
    def __init__(self, group=None, target=None, *args, **kwargs):
        if target == _run_in_subprocess:
            target = _run_in_subprocess_with_recording
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
        if pytest.is_replay or pytest.is_record:
            from promptflow.recording.local import RecordStorage

            RecordStorage.get_instance().delete_lock_file()
        if pytest.is_live:
            from promptflow.recording.local import delete_count_lock_file

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
        from promptflow.recording.local import RecordStorage, inject_async_with_recording, inject_sync_with_recording
        from promptflow.recording.record_mode import check_pydantic_v2

        check_pydantic_v2()
        file_path = RECORDINGS_TEST_CONFIGS_ROOT / "tracing.node_cache.shelve"
        RecordStorage.get_instance(file_path)

        patch_targets = {
            "promptflow.tracing._integrations._openai_injector.inject_sync": inject_sync_with_recording,
            "promptflow.tracing._integrations._openai_injector.inject_async": inject_async_with_recording,
        }
        start_patches(patch_targets)

    if is_live() and is_in_ci_pipeline():
        from promptflow.recording.local import inject_async_with_recording, inject_sync_with_recording

        patch_targets = {
            "promptflow.tracing._integrations._openai_injector.inject_sync": inject_sync_with_recording,
            "promptflow.tracing._integrations._openai_injector.inject_async": inject_async_with_recording,
        }
        start_patches(patch_targets)

    inject_openai_api()
    return patches


def _run_in_subprocess_with_recording(queue, func, args, kwargs):
    setup_recording_injection_if_enabled()
    return _run_in_subprocess(queue, func, args, kwargs)
