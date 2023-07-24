import contextvars
import logging
import threading
import time
from typing import Callable
from functools import wraps

from promptflow.utils.utils import set_context


class PropagatingThread(threading.Thread):
    """Thread class with a result/exception property to get the return/exception back."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._context = contextvars.copy_context()
        self.exception = None
        self.result = None

    def run(self):
        """Override Thread.run method."""
        set_context(self._context)
        try:
            if self._target:
                self.result = self._target(*self._args, **self._kwargs)
        except Exception as e:
            self.exception = e
        finally:
            # Avoid a refcycle if the thread is running a function with
            # an argument that has a member that points to the thread.
            del self._target, self._args, self._kwargs


class RepeatLogTimer(threading.Timer):
    """Repeat to log message every interval seconds until it is cancelled."""

    def __init__(
            self,
            interval_seconds: float,
            logger: logging.Logger,
            func_name: str):

        self._logger = logger
        self._func_name = func_name
        self._context = contextvars.copy_context()
        super().__init__(interval_seconds, function=None)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.cancel()

    def run(self):
        """Override Timer.run method."""
        # Set context variables from parent context.
        set_context(self._context)
        start_time = time.perf_counter()
        while not self.finished.wait(self.interval):
            if not self.finished.is_set():
                elapse_time = time.perf_counter() - start_time
                self._logger.warning(f"{self._func_name} has been running for {elapse_time:.0f} seconds.")
        self.finished.set()


def execute_func_with_timeout(func: Callable, timeout_seconds: float, func_name: str = None):
    """Execute a function in a daemon thread with timeout.

    After timeout, TimeoutError will be raised if the function is still running.
    """
    func_name = func_name if func_name else func.__name__

    thread = PropagatingThread(target=func)
    thread.daemon = True
    thread.start()
    thread.join(timeout=timeout_seconds)
    if thread.is_alive():
        raise TimeoutError(f"{func_name} timed out after {timeout_seconds} seconds")
    if thread.exception:
        raise thread.exception
    return thread.result


def timeout(timeout_seconds: float, func_name: str = None):
    """Decorator to set timeout for a function.

    After timeout, TimeoutError will be raised if the function is still running.
    """
    def decorator(func):
        @wraps(func)
        def f_timeout(*args, **kwargs):
            return execute_func_with_timeout(lambda: func(*args, **kwargs), timeout_seconds, func_name)
        return f_timeout
    return decorator
