# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------


import multiprocessing
import os
from pathlib import Path
from typing import Optional

from promptflow.executor import FlowExecutor


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
        multiprocessing_start_method = os.environ.get("PF_BATCH_METHOD", multiprocessing.get_start_method())
        sys_start_methods = multiprocessing.get_all_start_methods()
        if multiprocessing_start_method not in sys_start_methods:
            bulk_logger.warning(
                f"Failed to set start method to '{multiprocessing_start_method}', "
                f"start method {multiprocessing_start_method} is not in: {sys_start_methods}."
            )
            bulk_logger.info(f"Set start method to default {multiprocessing.get_start_method()}.")
            multiprocessing_start_method = multiprocessing.get_start_method()
        use_fork = multiprocessing_start_method in ["fork", "forkserver"]
        self._flow_file = flow_executor._flow_file
        self._connections = flow_executor._connections
        self._working_dir = flow_executor._working_dir
        self._use_fork = use_fork
        if isinstance(flow_executor, ScriptExecutor):
            self._storage = flow_executor._storage
        else:
            self._storage = flow_executor._run_tracker._storage
        self._flow_id = flow_executor._flow_id
        self._log_interval = flow_executor._log_interval
        self._line_timeout_sec = line_timeout_sec or LINE_TIMEOUT_SEC
        self._batch_timeout_sec = batch_timeout_sec
        self._output_dir = output_dir
        self._flow_create_kwargs = {
            "flow_file": flow_executor._flow_file,
            "connections": flow_executor._connections,
            "working_dir": flow_executor._working_dir,
            "line_timeout_sec": self._line_timeout_sec,
            "raise_ex": False,
        }
        # Will set to True if the batch run is timeouted.
        self._is_timeout = False
        self._worker_count = self._determine_worker_count(worker_count)

    def submit(self):
        # submit
        pass

    def shutdown(self):
        # shutdown
        pass
