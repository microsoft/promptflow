import contextvars
import pytest
import time
from io import StringIO
from logging import Logger, StreamHandler

from promptflow.utils.thread_utils import RepeatLogTimer, timeout


class DummyException(Exception):
    pass


@pytest.mark.unittest
class TestRepeatLogTimer:
    def test_context_manager(self):
        s = StringIO()
        logger = Logger('test_repeat_log_timer')
        logger.addHandler(StreamHandler(s))
        with RepeatLogTimer(interval_seconds=1, logger=logger, func_name='Test'):
            time.sleep(10)
        logs = s.getvalue().split('\n')
        for i in range(1, 10):
            assert logs[i - 1] == f'Test has been running for {i} seconds.'


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
        var = contextvars.ContextVar('test-var', default=None)
        var.set(1)

        @timeout(timeout_seconds=1)
        def func():
            return var.get() == 1
        assert func()
