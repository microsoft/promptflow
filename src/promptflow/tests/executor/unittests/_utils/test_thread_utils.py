import contextvars
import time
from io import StringIO
from logging import WARNING, Logger, StreamHandler

import pytest

from promptflow._utils.thread_utils import RepeatLogTimer, timeout
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


@pytest.mark.unittest
class TestTimeoutDecorator:
    def test_timeout(self):
        @timeout(timeout_seconds=1)
        def func():
            time.sleep(10)

        with pytest.raises(TimeoutError):
            func()

    def test_exception_is_raised(self):
        @timeout(timeout_seconds=1)
        def func():
            raise DummyException()

        with pytest.raises(DummyException):
            func()

    def test_result_is_return(self):
        @timeout(timeout_seconds=1)
        def func():
            return 1

        assert func() == 1

    def test_context_variables_are_preserved(self):
        var = contextvars.ContextVar("test-var", default=None)
        var.set(1)

        @timeout(timeout_seconds=1)
        def func():
            return var.get() == 1

        assert func()
