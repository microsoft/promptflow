# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from io import StringIO, TextIOBase
from typing import Dict

from promptflow._utils.logger_utils import flow_logger, logger, scrub_credentials


class NodeInfo:
    def __init__(self, run_id: str, node_name: str, line_number: int):
        self.run_id = run_id
        self.node_name = node_name
        self.line_number = line_number

    def __str__(self) -> str:
        return f"{self.node_name} in line {self.line_number} (index starts from 0)"


class NodeLogManager:
    """Replace sys.stdout and sys.stderr with NodeLogWriter.

    This class intercepts and saves logs to stdout/stderr when executing a node. For example:
    with NodeLogManager() as log_manager:
        print('test stdout')
        print('test stderr', file=sys.stderr)

    log_manager.get_logs() will return: {'stdout': 'test stdout\n', 'stderr': 'test stderr\n'}
    """

    def __init__(self, record_datetime=True):
        self.stdout_logger = NodeLogWriter(sys.stdout, record_datetime)
        self.stderr_logger = NodeLogWriter(sys.stderr, record_datetime, is_stderr=True)
        self.log_handler = None

    def __enter__(self):
        """Replace sys.stdout and sys.stderr with NodeLogWriter."""
        self._prev_stdout = sys.stdout
        self._prev_stderr = sys.stderr
        sys.stdout = self.stdout_logger
        sys.stderr = self.stderr_logger
        return self

    def __exit__(self, *args):
        """Restore sys.stdout and sys.stderr."""
        sys.stdout = self._prev_stdout
        sys.stderr = self._prev_stderr

    def set_node_context(self, run_id: str, node_name: str, line_number: int):
        """Set node context."""
        self.stdout_logger.set_node_info(run_id, node_name, line_number)
        self.stderr_logger.set_node_info(run_id, node_name, line_number)

    def clear_node_context(self, run_id):
        """Clear node context."""
        self.stdout_logger.clear_node_info(run_id)
        self.stderr_logger.clear_node_info(run_id)

    def get_logs(self, run_id) -> Dict[str, str]:
        return {
            "stdout": self.stdout_logger.get_log(run_id),
            "stderr": self.stderr_logger.get_log(run_id),
        }


class NodeLogWriter(TextIOBase):
    """Record node run logs."""

    DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S%z"

    def __init__(self, prev_stdout, record_datetime=True, is_stderr=False):
        self.run_id_to_stdout = dict()
        self._context = ContextVar("run_log_info", default=None)
        self._prev_out = prev_stdout
        self._record_datetime = record_datetime
        self._is_stderr = is_stderr

    def set_node_info(self, run_id: str, node_name: str, line_number: int = None):
        """Set node info to a context variable.

        After set node info, write method will write to stringio associated with this node.
        """
        run_log_info = NodeInfo(run_id, node_name, line_number)
        self._context.set(run_log_info)
        self.run_id_to_stdout.update({run_id: StringIO()})

    def clear_node_info(self, run_id: str):
        """Clear context variable associated with run id."""
        log_info: NodeInfo = self._context.get()
        if log_info and log_info.run_id == run_id:
            self._context.set(None)

        if run_id in self.run_id_to_stdout:
            self.run_id_to_stdout.pop(run_id)

    def get_log(self, run_id: str) -> str:
        """Get log associated with run id."""
        string_io: StringIO = self.run_id_to_stdout.get(run_id)
        if string_io is None:
            return None

        return string_io.getvalue()

    def write(self, s: str):
        """Override TextIO's write method and writes input string into a stringio

        The written string is compliant without any credentials.
        The string is also recorded to flow/bulk logger.
        If node info is not set, write to previous stdout.
        """
        log_info: NodeInfo = self._context.get()
        s = scrub_credentials(s)  # Remove credential from string.
        if log_info is None:
            self._prev_out.write(s)
        else:
            self._write_to_flow_log(log_info, s)
            stdout: StringIO = self.run_id_to_stdout.get(log_info.run_id)
            # When the line execution timeout is reached, all running nodes will be cancelled and node info will
            # be cleared. This will remove StringIO from self.run_id_to_stdout. For sync tools running in a worker
            # thread, they can't be stopped and self._context won't change in the worker
            # thread because it's a thread-local variable. Therefore, we need to check if StringIO is None here.
            if stdout is None:
                return
            if self._record_datetime and s != "\n":  # For line breaker, do not add datetime prefix.
                s = f"[{datetime.now(timezone.utc).strftime(self.DATETIME_FORMAT)}] {s}"
            stdout.write(s)

    def flush(self):
        """Override TextIO's flush method."""
        node_info: NodeInfo = self._context.get()
        if node_info is None:
            self._prev_out.flush()
        else:
            string_io = self.run_id_to_stdout.get(node_info.run_id)
            if string_io is not None:
                string_io.flush()

    def _write_to_flow_log(self, log_info: NodeInfo, s: str):
        """Save stdout log to flow_logger and stderr log to logger."""
        # If user uses "print('log message.')" to log, then
        # "write" method will be called twice and the second time input is only '\n'.
        # For this case, should not log '\n' in flow_logger.
        if s != "\n":
            if self._is_stderr:
                flow_log = f"[{str(log_info)}] stderr> " + s.rstrip("\n")
                # Log stderr in all scenarios so we can diagnose problems.
                logger.warning(flow_log)
            else:
                flow_log = f"[{str(log_info)}] stdout> " + s.rstrip("\n")
                # Log stdout only in flow mode.
                flow_logger.info(flow_log)
