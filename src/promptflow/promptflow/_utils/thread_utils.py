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
