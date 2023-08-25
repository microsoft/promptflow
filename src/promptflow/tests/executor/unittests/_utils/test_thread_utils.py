import time
from io import StringIO
from logging import WARNING, Logger, StreamHandler

import pytest

from promptflow._utils.thread_utils import RepeatLogTimer
from promptflow._utils.utils import generate_elapsed_time_messages


class DummyException(Exception):
    pass


@pytest.mark.unittest
class TestRepeatLogTimer:
    def test_context_manager(self):
        s = StringIO()
        logger = Logger("test_repeat_log_timer")
        logger.addHandler(StreamHandler(s))
        interval_seconds = 1
        start_time = time.perf_counter()
        with RepeatLogTimer(
            interval_seconds=interval_seconds,
            logger=logger,
            level=WARNING,
            log_message_function=generate_elapsed_time_messages,
            args=("Test", start_time, interval_seconds, None),
        ):
            time.sleep(10)
        logs = s.getvalue().split("\n")
        for i in range(1, 10):
            assert (
                logs[i - 1]
                == f"Test has been running for {i} seconds, "
                + "thread None cannot be found in sys._current_frames, "
                + "maybe it has been terminated due to unexpected errors."
            )
