# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

# This file is not for open source.


import logging
import sys
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from enum import Enum
from threading import RLock
from typing import Dict, List, Optional

from opencensus.ext.azure.log_exporter import AzureLogHandler

from promptflow._utils.credential_scrubber import CredentialScrubber
from promptflow._utils.logger_utils import (
    CredentialScrubberFormatter,
    FileHandler,
    FileHandlerConcurrentWrapper,
    LogContext,
    LOG_FORMAT,
    DATETIME_FORMAT,
)


class BlobFileHandler(FileHandler):
    """Write compliant log to a blob file in azure storage account."""

    def _get_stream_handler(self, file_path: str) -> logging.StreamHandler:
        """Override FileHandler's _get_stream_handler method."""
        from promptflow._utils.blob_utils import (
            BlobStream,
        )  # TODO: Move it to top of file.

        return logging.StreamHandler(BlobStream(file_path))


class FileType(Enum):
    Local = "Local"
    Blob = "Blob"


@dataclass
class SystemLogContext(LogContext):
    file_type: Optional[FileType] = FileType.Local
    app_insights_instrumentation_key: Optional[
        str
    ] = None  # If set, logs will also be sent to app insights.
    custom_dimensions: Optional[
        Dict[str, str]
    ] = None  # Custom dimension column in app insight log.

    def __enter__(self):
        self.loggers = [system_logger]
        # Set connection string and customer dimensions for telemetry log handler.
        if self.input_logger:
            self.loggers.append(self.input_logger)
        for logger in self.loggers:
            for log_handler in logger.handlers:
                if isinstance(log_handler, TelemetryLogHandler):
                    log_handler.set_connection_string(
                        self.app_insights_instrumentation_key
                    )
                    log_handler.set_or_update_context(self.custom_dimensions)
                    log_handler.set_credential_list(self.credential_list or [])

        super().__enter__()

    def __exit__(self, *args):
        super().__exit__(*args)
        # Flush telemetry log handler.
        for logger in self.loggers:
            for log_handler in logger.handlers:
                if isinstance(log_handler, TelemetryLogHandler):
                    log_handler.flush()

    def _set_log_path(self):
        """Override _set_log_path of parent class."""
        if not self.file_path:
            return

        if self.file_type == FileType.Local:
            super()._set_log_path()
        elif self.file_type == FileType.Blob:
            logger_list = self._get_loggers_to_set_path()
            for logger_ in logger_list:
                for log_handler in logger_.handlers:
                    if isinstance(log_handler, FileHandlerConcurrentWrapper):
                        handler = BlobFileHandler(self.file_path)
                        log_handler.handler = handler
        else:
            raise ValueError(f"Unsupported file type {self.file_type}.")


@contextmanager
def set_custom_dimensions_to_logger(
    input_logger: logging.Logger, custom_dimensions: Dict[str, str]
):
    for handler in input_logger.handlers:
        if isinstance(handler, TelemetryLogHandler):
            handler.set_or_update_context(custom_dimensions)
    try:
        yield
    finally:
        for handler in input_logger.handlers:
            if isinstance(handler, TelemetryLogHandler):
                handler.flush()


class TelemetryLogHandler(logging.Handler):
    """Write compliant log (no customer content) to app insights."""

    FORMAT = "%(message)s"
    CONNECTION_STRING = ""
    SINGLE_LOCK = RLock()

    def __init__(self):
        super().__init__()
        self._handler = None
        self._context = ContextVar("request_context", default=None)
        self._formatter = CredentialScrubberFormatter(
            scrub_customer_content=True,
            fmt=self.FORMAT,  # Telemetry log should not contain customer content.
        )

    @classmethod
    def get_instance(cls):
        with TelemetryLogHandler.SINGLE_LOCK:
            if not hasattr(TelemetryLogHandler, "_singleton"):
                TelemetryLogHandler._singleton = TelemetryLogHandler()
        return TelemetryLogHandler._singleton

    def set_connection_string(self, connection_string: Optional[str]):
        """Set connection string and azure log handler."""
        if not connection_string:
            return

        # If connection string is set already, then do not set again.
        if TelemetryLogHandler.CONNECTION_STRING == connection_string:
            return

        TelemetryLogHandler.CONNECTION_STRING = connection_string
        handler = AzureLogHandler(connection_string=connection_string)
        handler.setFormatter(self._formatter)
        self._handler = handler

    def set_or_update_context(self, context: Optional[Dict[str, str]]):
        """Set log context, such as request id, workspace info."""
        if context is None:
            return

        current_context: Dict = self._context.get()
        if current_context is None:
            self._context.set(context)
        else:
            current_context.update(context)

    def set_credential_list(self, credential_list: List[str]):
        """Set credential list, which will be scrubbed in logs."""
        self._formatter.set_credential_list(credential_list)

    def emit(self, record: logging.LogRecord):
        """Override logging.Handler's emit method."""
        if not self._handler:
            return

        # If the whole message is to be scrubbed, then do not emit.
        if self._formatter.format(record) == CredentialScrubber.PLACE_HOLDER:
            return

        # Add custom_dimensions to record
        record.custom_dimensions = self._get_custom_dimensions(record)
        # Set exc_info to None, otherwise this log will be sent to app insights's exception table.
        record.exc_info = None
        self._handler.emit(record)

    def reset_log_handler(self):
        """Reset handler."""
        if not TelemetryLogHandler.CONNECTION_STRING:
            return

        if self._handler:
            self._handler.flush()

        self._handler = AzureLogHandler(
            connection_string=TelemetryLogHandler.CONNECTION_STRING
        )
        self._handler.setFormatter(self._formatter)

    def close(self):
        """Close log handler."""
        if self._handler is None:
            return
        self._handler.close()

    def clear(self):
        """Clear context variable."""
        self._context.set(None)
        self._formatter.clear()

    def flush(self):
        """Flush log."""
        if self._handler is None:
            return
        self._handler.flush()

    def _get_custom_dimensions(self, record: logging.LogRecord) -> Dict[str, str]:
        custom_dimensions = self._context.get()
        if not custom_dimensions:
            custom_dimensions = dict()

        if hasattr(record, "custom_dimensions"):
            custom_dimensions.update(record.custom_dimensions)

        custom_dimensions.update(
            {
                "processId": record.process,
                "name": record.name,
            }
        )
        return custom_dimensions


def reset_telemetry_log_handler(input_logger: logging.Logger):
    for handler in input_logger.handlers:
        if isinstance(handler, TelemetryLogHandler):
            handler.reset_log_handler()


def close_telemetry_log_handler(input_logger: logging.Logger):
    for handler in input_logger.handlers:
        if isinstance(handler, TelemetryLogHandler):
            handler.close()


def _get_system_logger(
    logger_name,
    log_level: int = logging.DEBUG,
) -> logging.Logger:
    logger = logging.Logger(logger_name)
    logger.setLevel(log_level)
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(
        CredentialScrubberFormatter(
            scrub_customer_content=True, fmt=LOG_FORMAT, datefmt=DATETIME_FORMAT
        )
    )
    logger.addHandler(stdout_handler)
    logger.addHandler(TelemetryLogHandler.get_instance())
    return logger


# The system_logger will only capture logs in app insights, which will remain hidden from customers' view.
system_logger = _get_system_logger("promptflow-system")
