import os

ENVIRON_TEST_MODE = "PROMPT_FLOW_TEST_MODE"


class RecordMode:
    LIVE = "live"
    RECORD = "record"
    REPLAY = "replay"


def get_test_mode_from_environ() -> str:
    return os.getenv(ENVIRON_TEST_MODE, RecordMode.LIVE)


def is_record() -> bool:
    return get_test_mode_from_environ() == RecordMode.RECORD


def is_replay() -> bool:
    return get_test_mode_from_environ() == RecordMode.REPLAY


def is_live() -> bool:
    return get_test_mode_from_environ() == RecordMode.LIVE


def is_recording_enabled() -> bool:
    return is_record() or is_replay() or is_live()


def is_in_ci_pipeline():
    if os.environ.get("IS_IN_CI_PIPELINE") == "true":
        return True
    return False


def check_pydantic_v2():
    try:
        from importlib.metadata import version

        if version("pydantic") < "2.0.0":
            raise ImportError("pydantic version is less than 2.0.0. Recording cannot work properly.")
    except ImportError:
        raise ImportError("pydantic is not installed, this is required component for openai recording.")
