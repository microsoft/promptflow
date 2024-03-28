# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import contextvars
import logging
import threading

from promptflow._utils.utils import set_context


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


# Subclass of Thread to set context variables from parent context.
# Our logger is context-aware, FileHandlerConcurrentWrapper need to get FileHandler from the context.
# When we miss to set the context, log content in worker thread will not be written to the file.
class ThreadWithContextVars(threading.Thread):
    """A thread with context variables from the current context."""

    def __init__(self, group=None, target=None, name=None, args=(), kwargs=None, *, daemon=None):
        self._context = contextvars.copy_context()
        super().__init__(group=group, target=target, name=name, args=args, kwargs=kwargs, daemon=daemon)

    def run(self):
        """Override Thread.run method."""
        # Set context variables from parent context.
        set_context(self._context)
        super().run()
