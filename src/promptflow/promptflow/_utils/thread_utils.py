# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import contextvars
import logging
import threading
from functools import wraps
from typing import Callable

from promptflow._utils.utils import set_context


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
        self, interval_seconds: float, logger: logging.Logger, level: int, log_message_function, args: tuple = None
    ):
        self._logger = logger
        self._level = level
        self._log_message_function = log_message_function
        self._function_args = args if args else tuple()
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
        while not self.finished.wait(self.interval):
            if not self.finished.is_set():
                msgs = self._log_message_function(*self._function_args)
                for msg in msgs:
                    self._logger.log(self._level, msg)
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
