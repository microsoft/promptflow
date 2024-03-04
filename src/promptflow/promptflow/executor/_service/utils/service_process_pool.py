# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from pathlib import Path
from typing import Optional

from promptflow._constants import LINE_TIMEOUT_SEC
from promptflow._utils.process_utils import use_fork_for_process
from promptflow.executor import FlowExecutor
from promptflow.executor._script_executor import ScriptExecutor


class ServiceProcessPool:
    _instance = None
    _init = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ServiceProcessPool, cls).__new__(cls)
        return cls._instance

    def __init__(
        self,
        flow_executor: FlowExecutor,
        line_count: int,
        output_dir: Path,
        line_timeout_sec: Optional[int] = None,
        worker_count: Optional[int] = None,
    ):
        if self._init:
            return

        # create process

        # create thread

        # create other
        self._init = True

        self._line_count = line_count

        # Determine how to start the processes
        self._use_fork = use_fork_for_process()

        self._flow_file = flow_executor._flow_file
        self._connections = flow_executor._connections
        self._working_dir = flow_executor._working_dir
        # ?????? no need
        if isinstance(flow_executor, ScriptExecutor):
            self._storage = flow_executor._storage
        else:
            self._storage = flow_executor._run_tracker._storage

        self._flow_id = flow_executor._flow_id
        self._line_timeout_sec = line_timeout_sec or LINE_TIMEOUT_SEC
        self._output_dir = output_dir

        self._flow_create_kwargs = {
            "flow_file": flow_executor._flow_file,
            "connections": flow_executor._connections,
            "working_dir": flow_executor._working_dir,
            "line_timeout_sec": self._line_timeout_sec,
            "raise_ex": False,
        }
        self._worker_count = self._determine_worker_count(worker_count)

    def submit(self):
        # submit
        pass

    def shutdown(self):
        # shutdown
        pass
