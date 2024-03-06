# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from pathlib import Path
from typing import Any, Mapping, Optional

from promptflow.executor import FlowExecutor
from promptflow.executor._line_execution_process_pool_copy import LineExecutionProcessPool
from promptflow.executor._service._errors import UninitializedError
from promptflow.executor._service.contracts.batch_request import AggregationRequest, LineExecutionRequest
from promptflow.storage._executor_service_storage import ExecutorServiceStorage


class BatchCoordinator:
    _instance = None
    _init = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(BatchCoordinator, cls).__new__(cls)
        return cls._instance

    def __init__(
        self,
        working_dir: Path,
        flow_file: Path,
        output_dir: Path,
        connections: Optional[Mapping[str, Any]] = None,
        worker_count: Optional[int] = None,
        line_timeout_sec: Optional[int] = None,
    ):
        if self._init:
            return
        # init flow executor and validate flow
        storage = ExecutorServiceStorage(output_dir)
        self._flow_executor = FlowExecutor.create(flow_file, connections, working_dir, storage=storage, raise_ex=False)
        self._process_pool = LineExecutionProcessPool(
            output_dir,
            self._flow_executor,
            worker_count=worker_count,
            line_timeout_sec=line_timeout_sec,
        )
        self._init = True

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            raise UninitializedError(
                "Please initialize the executor service with the '/initialize' api before sending execution requests."
            )
        return cls._instance

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
