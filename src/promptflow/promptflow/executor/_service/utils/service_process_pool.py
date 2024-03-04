# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------


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

    def submit(self):
        # submit
        pass

    def shutdown(self):
        # shutdown
        pass
