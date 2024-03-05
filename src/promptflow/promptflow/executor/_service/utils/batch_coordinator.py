# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from pathlib import Path
from typing import Optional

from promptflow.executor import FlowExecutor
from promptflow.executor._line_execution_process_pool_copy import LineExecutionProcessPool
from promptflow.executor._service.contracts.batch_request import AggregationRequest, LineExecutionRequest


class BatchCoordinator:
    _instance = None
    _init = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(BatchCoordinator, cls).__new__(cls)
        return cls._instance

    def __init__(
        self,
        output_dir: Path,
        flow_executor: FlowExecutor,
        worker_count: Optional[int] = None,
        line_timeout_sec: Optional[int] = None,
    ):
        if self._init:
            return
        self._process_pool = LineExecutionProcessPool(
            output_dir,
            flow_executor,
            worker_count=worker_count,
            line_timeout_sec=line_timeout_sec,
        )
        self._flow_executor = flow_executor
        self._init = True

    def start(self):
        self._process_pool.start()

    async def exec_line(self, request: LineExecutionRequest):
        return await self._process_pool.submit(request.inputs, request.run_id, request.line_number)

    def exec_aggregation(self, request: AggregationRequest):
        with self._flow_executor._run_tracker.node_log_manager:
            return self._flow_executor._exec_aggregation(
                request.batch_inputs, request.aggregation_inputs, request.run_id
            )

    def shutdown(self):
        self._process_pool.end()
        self._init = False
        self._instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            raise Exception("Singleton instance has not been initialized yet.")
        return cls._instance
