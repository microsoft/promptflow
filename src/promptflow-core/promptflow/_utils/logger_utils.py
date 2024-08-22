# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

# This file is for open source,
# so it should not contain any dependency on azure or azureml-related packages.

import contextlib
import json
import logging
import os
import sys
from contextvars import ContextVar
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import List, Optional, Tuple

from promptflow._constants import LINE_NUMBER_WIDTH, PF_LOGGING_LEVEL
from promptflow._utils.credential_scrubber import CredentialScrubber
from promptflow._utils.exception_utils import ExceptionPresenter
from promptflow.contracts.run_mode import RunMode

# The maximum length of logger name is 18 ("promptflow-runtime").
# The maximum digit length of process id is 5. Fix the field width to 7.
# So fix the length of these fields in the formatter.
# May need to change if logger name/process id length changes.
LOG_FORMAT = "%(asctime)s %(process)7d %(name)-18s %(levelname)-8s %(message)s"
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S %z"


def _get_format_for_logger(default_log_format: str = None, default_date_format: str = None) -> Tuple[str, str]:
    """
    Get the logging format and date format for logger.

    This function attempts to find the handler of the root logger with a configured formatter.
    If such a handler is found, it returns the format and date format used by this handler.
    This can be configured through logging.basicConfig. If no configured formatter is found,
    it defaults to LOG_FORMAT and DATETIME_FORMAT.
    """
    log_format = os.environ.get("PF_LOG_FORMAT") or default_log_format or LOG_FORMAT
    datetime_format = os.environ.get("PF_LOG_DATETIME_FORMAT") or default_date_format or DATETIME_FORMAT
    return log_format, datetime_format


class CredentialScrubberFormatter(logging.Formatter):
    """Formatter that scrubs credentials in logs."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._default_scrubber = CredentialScrubber()
        self._context_var = ContextVar("credential_scrubber", default=None)

    @property
    def credential_scrubber(self):
        credential_scrubber = self._context_var.get()
        if credential_scrubber:
            return credential_scrubber
        return self._default_scrubber

    def set_credential_list(self, credential_list: List[str]):
        """Set credential list, which will be scrubbed in logs."""
        credential_scrubber = CredentialScrubber()
        for c in credential_list:
            credential_scrubber.add_str(c)
        self._context_var.set(credential_scrubber)

    def clear(self):
        """Clear context variable."""
        self._context_var.set(None)

    def format(self, record):
        """Override logging.Formatter's format method and remove credentials from log."""
        s: str = super().format(record)

        s = self._handle_traceback(s, record)
        s = self._handle_customer_content(s, record)
        return self.credential_scrubber.scrub(s)

    def _handle_customer_content(self, s: str, record: logging.LogRecord) -> str:
        """Handle customer content in log message.

        Derived class can override this method to handle customer content in log.
        """
        # If log record does not have "customer_content" field, return input logging string directly.
        if not hasattr(record, "customer_content"):
            return s

        customer_content = record.customer_content

        if isinstance(customer_content, Exception):
            # If customer_content is an exception, convert it to string.
            customer_str = self._convert_exception_to_str(customer_content)
        elif isinstance(customer_content, str):
            customer_str = customer_content
        else:
            customer_str = str(customer_content)

        return s.replace("{customer_content}", customer_str)

    def _handle_traceback(self, s: str, record: logging.LogRecord) -> str:
        """Interface method for handling traceback in log message.

        Derived class can override this method to handle traceback in log.
        """
        return s

    def _convert_exception_to_str(self, ex: Exception) -> str:
        """Convert exception a user-friendly string."""
        try:
            return json.dumps(ExceptionPresenter.create(ex).to_dict(include_debug_info=True), indent=2)
        except:  # noqa: E722
            return str(ex)


class FileHandler:
    """Write compliant log to a file."""

    def __init__(self, file_path: str, formatter: Optional[logging.Formatter] = None):
        self._stream_handler = self._get_stream_handler(file_path)
        if formatter is None:
            # Default formatter to scrub credentials in log message, exception and stack trace.
            fmt, datefmt = _get_format_for_logger()
            self._formatter = CredentialScrubberFormatter(fmt=fmt, datefmt=datefmt)
        else:
            self._formatter = formatter
        self._stream_handler.setFormatter(self._formatter)

    def set_credential_list(self, credential_list: List[str]):
        """Set credential list, which will be scrubbed in logs."""
        self._formatter.set_credential_list(credential_list)

    def emit(self, record: logging.LogRecord):
        """Write logs."""
        self._stream_handler.emit(record)

    def close(self):
        """Close stream handler."""
        self._stream_handler.close()
        self._formatter.clear()

    def _get_stream_handler(self, file_path) -> logging.StreamHandler:
        """This method can be overridden by derived class to save log file in cloud."""
        return logging.FileHandler(file_path, encoding="UTF-8")


class FileHandlerConcurrentWrapper(logging.Handler):
    """Wrap context-local FileHandler instance for thread safety.

    A logger instance can write different log to different files in different contexts.
    """

    def __init__(self):
        super().__init__()
        self._context_var = ContextVar("handler", default=None)

    @property
    def handler(self) -> FileHandler:
        return self._context_var.get()

    @handler.setter
    def handler(self, handler: FileHandler):
        self._context_var.set(handler)

    def emit(self, record: logging.LogRecord):
        """Override logging.Handler's emit method.

        Get inner file handler in current context and write log.
        """
        stream_handler: FileHandler = self._context_var.get()
        if stream_handler is None:
            return
        stream_handler.emit(record)

    def clear(self):
        """Close file handler and clear context variable."""
        handler: FileHandler = self._context_var.get()
        if handler:
            try:
                handler.close()
            except:  # NOQA: E722
                # Do nothing if handler close failed.
                pass
        self._context_var.set(None)


valid_logging_level = {"CRITICAL", "FATAL", "ERROR", "WARN", "WARNING", "INFO", "DEBUG", "NOTSET"}


def get_pf_logging_level(default=logging.INFO):
    logging_level = os.environ.get(PF_LOGGING_LEVEL, None)
    if logging_level not in valid_logging_level:
        # Fall back to info if user input is invalid.
        logging_level = default
    return logging_level


def get_logger(name: str) -> logging.Logger:
    """Get logger used during execution."""
    logger = logging.Logger(name)
    logger.setLevel(get_pf_logging_level())
    logger.addHandler(FileHandlerConcurrentWrapper())
    stdout_handler = logging.StreamHandler(sys.stdout)
    fmt, datefmt = _get_format_for_logger()
    stdout_handler.setFormatter(CredentialScrubberFormatter(fmt=fmt, datefmt=datefmt))
    logger.addHandler(stdout_handler)
    return logger


# Logs by flow_logger will only be shown in flow mode.
# These logs should contain all detailed logs from executor and runtime.
flow_logger = get_logger("execution.flow")

# Logs by bulk_logger will only be shown in bulktest and eval modes.
# These logs should contain overall progress logs and error logs.
bulk_logger = get_logger("execution.bulk")

# Logs by logger will be shown in all the modes above,
# such as error logs.
logger = get_logger("execution")

# Logs by service_logger will be shown in executor service mode.
service_logger = get_logger("execution.service")


logger_contexts = []


@dataclass
class LogContext:
    """A context manager to setup logger context for input_logger, logger, flow_logger and bulk_logger."""

    file_path: str  # Log file path.
    run_mode: Optional[RunMode] = RunMode.Test
    credential_list: Optional[List[str]] = None  # These credentials will be scrubbed in logs.
    input_logger: logging.Logger = None  # If set, then context will also be set for input_logger.
    flow_logs_folder: Optional[str] = None  # Used in batch mode to specify the folder for flow logs.
    line_number: Optional[int] = None  # Used in batch mode to specify the line log file name.

    # Before, we only have one FileHandlerConcurrentWrapper for any run mode.
    # Now, we have two for batch run mode, one for whole run log, one for single line log.
    # For single line log handlers, we create and remove them in __enter__ and __exit__ method,
    # to avoid setting same logger path for 2 handlers.
    temporary_flow_log_handlers = []

    def get_initializer(self):
        return partial(
            LogContext,
            file_path=self.file_path,
            run_mode=self.run_mode,
            credential_list=self.credential_list,
            flow_logs_folder=self.flow_logs_folder,
        )

    @staticmethod
    def get_current() -> Optional["LogContext"]:
        global logger_contexts
        if logger_contexts:
            return logger_contexts[-1]
        return None

    @staticmethod
    def set_current(context: "LogContext"):
        global logger_contexts
        if isinstance(context, LogContext):
            logger_contexts.append(context)

    @staticmethod
    def clear_current():
        global logger_contexts
        if logger_contexts:
            logger_contexts.pop()

    def __enter__(self):
        self._set_log_path()
        self._add_batch_run_flow_logs_handler()
        self._set_credential_list()
        LogContext.set_current(self)

    def __exit__(self, *args):
        """Clear context-local variables."""
        all_logger_list = [logger, flow_logger, bulk_logger]
        if self.input_logger:
            all_logger_list.append(self.input_logger)
        for logger_ in all_logger_list:
            for handler in logger_.handlers:
                if isinstance(handler, FileHandlerConcurrentWrapper):
                    handler.clear()
                elif isinstance(handler.formatter, CredentialScrubberFormatter):
                    handler.formatter.clear()
            for handlers_to_remove in self.temporary_flow_log_handlers:
                logger_.removeHandler(handlers_to_remove)
        self.temporary_flow_log_handlers.clear()
        LogContext.clear_current()

    def _set_log_path(self):
        if not self.file_path:
            return

        logger_list = self._get_loggers_to_set_path()
        for logger_ in logger_list:
            for log_handler in logger_.handlers:
                if isinstance(log_handler, FileHandlerConcurrentWrapper):
                    handler = FileHandler(self.file_path)
                    log_handler.handler = handler

    # During __enter__ method, add FileHandlerConcurrentWrapper for batch run mode's single line execution log.
    # And remove it during __exit__ method.
    def _add_batch_run_flow_logs_handler(self):
        if self.run_mode != RunMode.Batch or self.flow_logs_folder is None or self.line_number is None:
            return

        file_name = f"{str(self.line_number).zfill(LINE_NUMBER_WIDTH)}.log"
        path = Path(self.flow_logs_folder) / file_name
        for logger_ in self._get_batch_run_flow_loggers_list():
            flow_log_handler = FileHandlerConcurrentWrapper()
            handler = FileHandler(path)
            flow_log_handler.handler = handler
            logger_.addHandler(flow_log_handler)
            self.temporary_flow_log_handlers.append(flow_log_handler)

    def _set_credential_list(self):
        # Set credential list to all loggers.
        all_logger_list = self._get_execute_loggers_list()
        if self.input_logger:
            all_logger_list.append(self.input_logger)
        credential_list = self.credential_list or []
        for logger_ in all_logger_list:
            for handler in logger_.handlers:
                if isinstance(handler, FileHandlerConcurrentWrapper) and handler.handler:
                    handler.handler.set_credential_list(credential_list)
                elif isinstance(handler.formatter, CredentialScrubberFormatter):
                    handler.formatter.set_credential_list(credential_list)

    def _get_loggers_to_set_path(self) -> List[logging.Logger]:
        logger_list = [logger]
        if self.input_logger:
            logger_list.append(self.input_logger)

        # For Batch run mode, set log path for bulk_logger,
        # otherwise for flow_logger.
        if self.run_mode == RunMode.Batch:
            logger_list.append(bulk_logger)
        else:
            logger_list.append(flow_logger)
        return logger_list

    @classmethod
    def _get_execute_loggers_list(cls) -> List[logging.Logger]:
        # return all loggers for executor
        return [logger, flow_logger, bulk_logger]

    @classmethod
    def _get_batch_run_flow_loggers_list(cls) -> List[logging.Logger]:
        # Exclude bulk_logger for line execution log.
        return [logger, flow_logger]


def update_log_path(log_path: str, input_logger: logging.Logger = None):
    logger_list = [logger, bulk_logger, flow_logger]
    if input_logger:
        logger_list.append(input_logger)
    for logger_ in logger_list:
        update_single_log_path(log_path, logger_)


def update_single_log_path(log_path: str, logger_: logging.Logger):
    for wrapper in logger_.handlers:
        if isinstance(wrapper, FileHandlerConcurrentWrapper):
            handler: FileHandler = wrapper.handler
            if handler:
                wrapper.handler = type(handler)(log_path, handler._formatter)


def scrub_credentials(s: str):
    """Scrub credentials in string s.

    For example, for input string: "print accountkey=accountKey", the output will be:
    "print accountkey=**data_scrubbed**"
    """
    for h in logger.handlers:
        if isinstance(h, FileHandlerConcurrentWrapper):
            if h.handler and h.handler._formatter:
                credential_scrubber = h.handler._formatter.credential_scrubber
                if credential_scrubber:
                    return credential_scrubber.scrub(s)
    return CredentialScrubber().scrub(s)


class LoggerFactory:
    _existing_loggers = [logger, flow_logger, bulk_logger, service_logger]
    _disabled = False

    @staticmethod
    def get_logger(name: str, verbosity: int = logging.INFO, target_stdout: bool = False):
        logger = logging.getLogger(name)
        if logger not in LoggerFactory._existing_loggers:
            LoggerFactory._existing_loggers.append(logger)
            logger.disabled = LoggerFactory._disabled
        logger.propagate = False
        # Use env var at first, then use verbosity
        verbosity = get_pf_logging_level(default=None) or verbosity
        logger.setLevel(verbosity)
        if not LoggerFactory._find_handler(logger, logging.StreamHandler):
            LoggerFactory._add_handler(logger, verbosity, target_stdout)
        # TODO: Find a more elegant way to set the logging level for azure.core.pipeline.policies._universal
        azure_logger = logging.getLogger("azure.core.pipeline.policies._universal")
        azure_logger.setLevel(logging.DEBUG)
        LoggerFactory._add_handler(azure_logger, logging.DEBUG, target_stdout)
        return logger

    @staticmethod
    def _find_handler(logger: logging.Logger, handler_type: type) -> Optional[logging.Handler]:
        for log_handler in logger.handlers:
            if isinstance(log_handler, handler_type):
                return log_handler
        return None

    @staticmethod
    def _add_handler(logger: logging.Logger, verbosity: int, target_stdout: bool = False) -> None:
        # set target_stdout=True can log data into sys.stdout instead of default sys.stderr, in this way
        # logger info and python print result can be synchronized
        handler = logging.StreamHandler(stream=sys.stdout) if target_stdout else logging.StreamHandler()
        fmt, datefmt = _get_format_for_logger(default_log_format="[%(asctime)s][%(name)s][%(levelname)s] - %(message)s")
        formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)
        handler.setFormatter(formatter)
        handler.setLevel(verbosity)
        logger.addHandler(handler)

    @staticmethod
    @contextlib.contextmanager
    def disable_all_loggers():
        """Disable all loggers."""
        #  If LoggerFactory is already disabled, do nothing
        if LoggerFactory._disabled:
            yield
            return
        try:
            LoggerFactory._disabled = True
            for each_logger in LoggerFactory._existing_loggers:
                each_logger.disabled = True
            yield
        finally:
            for each_logger in LoggerFactory._existing_loggers:
                each_logger.disabled = False
            LoggerFactory._disabled = False


def get_cli_sdk_logger():
    """Get logger used by CLI SDK."""
    # cli sdk logger default logging level is WARNING
    # here the logger name "promptflow" is from promptflow._sdk._constants.LOGGER_NAME,
    # to avoid circular import error, use plain string here instead of importing from _constants
    # because this function is also called in _prepare_home_dir which is in _constants
    return LoggerFactory.get_logger("promptflow", verbosity=logging.WARNING)
