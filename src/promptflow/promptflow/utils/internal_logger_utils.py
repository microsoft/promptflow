# This file is not for open source.


import logging
from contextvars import ContextVar
from dataclasses import dataclass
from enum import Enum
from opencensus.ext.azure.log_exporter import AzureLogHandler
from typing import Dict, Optional, List

from promptflow.utils.logger_utils import (
    CredentialScrubberFormatter,
    FileHandler,
    FileHandlerConcurrentWrapper,
    LogContext,
)
from promptflow.utils.credential_scrubber import CredentialScrubber


class BlobFileHandler(FileHandler):
    """Write compliant log to a blob file in azure storage account."""
    def _get_stream_handler(self, file_path: str) -> logging.StreamHandler:
        """Override FileHandler's _get_stream_handler method."""
        from promptflow.utils.blob_utils import BlobStream  # TODO: Move it to top of file.
        return logging.StreamHandler(BlobStream(file_path))


class FileType(Enum):
    Local = "Local"
    Blob = "Blob"


@dataclass
class SystemLogContext(LogContext):
    file_type: Optional[FileType] = FileType.Local
    app_insights_instrumentation_key: Optional[str] = None  # If set, logs will also be sent to app insights.
    custom_dimensions: Optional[Dict[str, str]] = None  # Custom dimension column in app insight log.

    def __enter__(self):
        # Set connection string and customer dimensions for telemetry log handler.
        if self.input_logger:
            for log_handler in self.input_logger.handlers:
                if isinstance(log_handler, TelemetryLogHandler):
                    log_handler.set_connection_string(self.app_insights_instrumentation_key)
                    log_handler.set_context(self.custom_dimensions)

        super().__enter__()

    def __exit__(self, *args):
        super().__exit__(*args)
        # Clear context variabel of telemetry log handler.
        if self.input_logger:
            for log_handler in self.input_logger.handlers:
                if isinstance(log_handler, TelemetryLogHandler):
                    log_handler.clear()

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


class TelemetryLogHandler(logging.Handler):
    """Write compliant log (no customer content) to app insights."""
    FORMAT = "%(message)s"
    CONNECTION_STRING = ""

    def __init__(self):
        super().__init__()
        self._handler = None
        self._context = ContextVar('request_context', default=None)
        self._formatter = CredentialScrubberFormatter(
            scrub_customer_content=True,  # Telemetry log should not contain customer content.
            fmt=self.FORMAT)

    def set_connection_string(self, connection_string: Optional[str]):
        """Set connection string and azure log handler."""
        if not connection_string:
            return

        # Set connection string.
        if TelemetryLogHandler.CONNECTION_STRING != connection_string:
            TelemetryLogHandler.CONNECTION_STRING = connection_string

        handler = AzureLogHandler(connection_string=connection_string)
        handler.setFormatter(self._formatter)
        self._handler = handler

    def set_context(self, context: Optional[Dict[str, str]]):
        """Set log context, such as request id, workspace info."""
        if context is None:
            return
        self._context.set(context)

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
        if not self._handler:
            return

        connection_str = self._handler.options.get('connection_string')
        if not connection_str:
            return

        self._handler = AzureLogHandler(connection_string=connection_str)
        self._handler.setFormatter(self._formatter)

    def clear(self):
        """Close handler and clear context variable."""
        if self._handler:
            self._handler.close()
        self._context.set(None)
        self._formatter.clear()

    def _get_custom_dimensions(self, record: logging.LogRecord) -> Dict[str, str]:
        custom_dimensions = self._context.get()
        if not custom_dimensions:
            custom_dimensions = dict()

        if hasattr(record, "custom_dimensions"):
            custom_dimensions.update(record.custom_dimensions)

        custom_dimensions.update({
            "processId": record.process,
            "name": record.name,
        })
        return custom_dimensions


def reset_telemetry_log_handler(input_logger: logging.Logger):
    for handler in input_logger.handlers:
        if isinstance(handler, TelemetryLogHandler):
            handler.reset_log_handler()
