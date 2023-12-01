from pathlib import Path

import pytest
from pytest_mock import MockerFixture
from sdk_cli_test.recording_utilities import RecordStorage, mock_tool, recording_array_extend, recording_array_reset

PROMPTFLOW_ROOT = Path(__file__) / "../../.."
RECORDINGS_TEST_CONFIGS_ROOT = Path(PROMPTFLOW_ROOT / "tests/test_configs/node_recordings").resolve()


@pytest.fixture
def recording_file_override(request: pytest.FixtureRequest, mocker: MockerFixture):
    if RecordStorage.is_replaying_mode() or RecordStorage.is_recording_mode():
        file_path = RECORDINGS_TEST_CONFIGS_ROOT / "executor_node_cache.shelve"
        RecordStorage.get_instance(file_path)
    yield


@pytest.fixture
def recording_injection(mocker: MockerFixture, recording_file_override):
    if RecordStorage.is_replaying_mode() or RecordStorage.is_recording_mode():
        mocker.patch("promptflow._core.tool.tool", mock_tool)
        mocker.patch("promptflow._internal.tool", mock_tool)
    try:
        yield (RecordStorage.is_replaying_mode() or RecordStorage.is_recording_mode(), recording_array_extend)
    finally:
        if RecordStorage.is_replaying_mode() or RecordStorage.is_recording_mode():
            RecordStorage.get_instance().delete_lock_file()
        recording_array_reset()
