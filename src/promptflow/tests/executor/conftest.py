import sys
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

PROMPTFLOW_ROOT = Path(__file__) / "../../.."
RECORDINGS_TEST_CONFIGS_ROOT = Path(PROMPTFLOW_ROOT / "tests/test_configs/node_recordings").resolve()


@pytest.fixture
def recording_file_override(request: pytest.FixtureRequest, mocker: MockerFixture):
    sys.path.insert(1, (Path(__file__).parent.parent / "sdk_cli_test").resolve().as_posix())
    from recording_utilities import RecordStorage

    if RecordStorage.is_replaying_mode() or RecordStorage.is_recording_mode():
        file_path = RECORDINGS_TEST_CONFIGS_ROOT / "node_cache.shelve"
        RecordStorage.get_instance(file_path)
    yield


@pytest.fixture
def recording_injection(mocker: MockerFixture, recording_file_override):
    sys.path.insert(1, (Path(__file__).parent.parent / "sdk_cli_test").resolve().as_posix())
    from recording_utilities import (
        RecordStorage,
        mock_call_func,
        mock_call_func_async,
        recording_array_extend,
        recording_array_reset,
    )

    if RecordStorage.is_replaying_mode() or RecordStorage.is_recording_mode():
        mocker.patch("promptflow._core.tool.call_func", mock_call_func)
        mocker.patch("promptflow._core.tool.call_func_async", mock_call_func_async)
    yield (RecordStorage.is_replaying_mode() or RecordStorage.is_recording_mode(), recording_array_extend)
    if RecordStorage.is_replaying_mode() or RecordStorage.is_recording_mode():
        RecordStorage.get_instance().delete_lock_file()
        recording_array_reset()
