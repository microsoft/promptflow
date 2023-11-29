from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from .recording_utilities import RecordFileMissingException, RecordItemMissingException, RecordStorage

PROMPTFLOW_ROOT = Path(__file__) / "../../.."
RECORDINGS_TEST_CONFIGS_ROOT = Path(PROMPTFLOW_ROOT / "tests/test_configs/node_recordings").resolve()


def mock_call_func(func, args, kwargs):
    if type(func).__name__ == "partial":
        func_wo_partial = func.func
    else:
        func_wo_partial = func
    if (
        func_wo_partial.__qualname__.startswith("AzureOpenAI")
        or func_wo_partial.__qualname__.startswith("OpenAI")
        or func_wo_partial.__qualname__ == "fetch_text_content_from_url"
        or func_wo_partial.__qualname__ == "my_python_tool"
    ):
        input_dict = {}
        for key in kwargs:
            input_dict[key] = kwargs[key]
        if type(func).__name__ == "partial":
            input_dict["_args"] = func.args
            for key in func.keywords:
                input_dict[key] = func.keywords[key]
        else:
            input_dict["_args"] = []
        input_dict["_func"] = func_wo_partial.__qualname__
        # Replay mode will direct return item from record file
        if RecordStorage.is_replaying_mode():
            obj = RecordStorage.get_instance().get_record(input_dict)
            return obj

        # Record mode will record item to record file
        if RecordStorage.is_recording_mode():
            # If already recorded, use previous result
            # If record item missing, call related functions and record result
            try:
                obj = RecordStorage.get_instance().get_record(input_dict)
            except (RecordItemMissingException, RecordFileMissingException):
                obj_original = func(*args, **kwargs)
                obj = RecordStorage.get_instance().set_record(input_dict, obj_original)
            # More exceptions should just raise
        else:
            obj = func(*args, **kwargs)
        return obj
    return func(*args, **kwargs)


async def mock_call_func_async(func, args, kwargs):
    if type(func).__name__ == "partial":
        func_wo_partial = func.func
    else:
        func_wo_partial = func
    if (
        func_wo_partial.__qualname__.startswith("AzureOpenAI")
        or func_wo_partial.__qualname__.startswith("OpenAI")
        or func_wo_partial.__qualname__ == "fetch_text_content_from_url"
        or func_wo_partial.__qualname__ == "my_python_tool"
    ):
        input_dict = {}
        for key in kwargs:
            input_dict[key] = kwargs[key]
        if type(func).__name__ == "partial":
            input_dict["_args"] = func.args
            for key in func.keywords:
                input_dict[key] = func.keywords[key]
        else:
            input_dict["_args"] = []
        input_dict["_func"] = func_wo_partial.__qualname__
        # Replay mode will direct return item from record file
        if RecordStorage.is_replaying_mode():
            obj = RecordStorage.get_instance().get_record(input_dict)
            return obj

        # Record mode will record item to record file
        if RecordStorage.is_recording_mode():
            # If already recorded, use previous result
            # If record item missing, call related functions and record result
            try:
                obj = RecordStorage.get_instance().get_record(input_dict)
            except (RecordItemMissingException, RecordFileMissingException):
                obj_original = await func(*args, **kwargs)
                obj = RecordStorage.get_instance().set_record(input_dict, obj_original)
            # More exceptions should just raise
        else:
            obj = await func(*args, **kwargs)
        return obj
    return await func(*args, **kwargs)


@pytest.fixture
def recording_file_override(request: pytest.FixtureRequest, mocker: MockerFixture):
    if RecordStorage.is_replaying_mode() or RecordStorage.is_recording_mode():
        file_path = RECORDINGS_TEST_CONFIGS_ROOT / "node_cache.shelve"
        RecordStorage.get_instance(file_path)
    yield


@pytest.fixture
def recording_injection(mocker: MockerFixture, recording_file_override):
    if RecordStorage.is_replaying_mode() or RecordStorage.is_recording_mode():
        mocker.patch("promptflow._core.tool.call_func", mock_call_func)
        mocker.patch("promptflow._core.tool.call_func_async", mock_call_func_async)
    yield
