import re
import sys
import threading
import time
from io import StringIO
from logging import WARNING, Logger, StreamHandler

import pytest

from promptflow._utils.thread_utils import RepeatLogTimer, create_thread_with_context_vars
from promptflow._utils.utils import generate_elapsed_time_messages


class DummyException(Exception):
    pass


@pytest.mark.skipif(sys.platform == "darwin", reason="Skip on Mac")
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
            time.sleep(10.5)
        logs = s.getvalue().split("\n")
        logs = [log for log in logs if log]
        log_pattern = re.compile(
            r"^Test has been running for [0-9]+ seconds, thread None cannot be found in sys._current_frames, "
            r"maybe it has been terminated due to unexpected errors.$"
        )
        assert logs, "Logs are empty."
        for log in logs:
            assert re.match(log_pattern, log), f"The wrong log: {log}"


def test_create_thread_with_context_vars_assert_arguments():
    # Collect exception raised by worker thread.
    thread_exceptions = []

    def target_function(args, **kwargs):
        try:
            assert args == "args"
            assert kwargs == {"key": "value"}
        except Exception as e:
            thread_exceptions.append(e)

    thread = create_thread_with_context_vars(target_function, target_args=("args",), target_kwargs={"key": "value"})
    start_and_assert_thread(thread, thread_exceptions)


def test_create_thread_with_context_vars_assert_daemon():
    # Collect exception raised by worker thread.
    thread_exceptions = []

    def target_function(is_deamon):
        try:
            assert threading.current_thread().daemon == is_deamon
        except Exception as e:
            thread_exceptions.append(e)

    thread = create_thread_with_context_vars(target_function, daemon=True, target_args=(True,))
    start_and_assert_thread(thread, thread_exceptions)

    thread = create_thread_with_context_vars(target_function, daemon=False, target_args=(False,))
    start_and_assert_thread(thread, thread_exceptions)


def start_and_assert_thread(thread, thread_exceptions):
    thread.start()
    thread.join()
    assert not thread.is_alive()
    if thread_exceptions:
        # Re-raise the exception in the main thread to make the test fail.
        raise thread_exceptions[0]
