# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from pathlib import Path
from typing import Any, Mapping, Optional

from promptflow._constants import OutputsFolderName
from promptflow._utils.multimedia_utils import process_multimedia_in_run_info
from promptflow.executor import FlowExecutor
from promptflow.executor._line_execution_process_pool import LineExecutionProcessPool
from promptflow.executor._service._errors import UninitializedError
from promptflow.executor._service.contracts.batch_request import AggregationRequest, LineExecutionRequest
from promptflow.storage._run_storage import DummyRunStorage


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
        # Init flow executor and validate flow
        self._output_dir = output_dir

        # The storage of FlowExecutor will be passed to LineExecutionProcessPool
        # and responsible for persisting the run info during line execution.

        # So we pass DummyRunStorage to FlowExecutor because we don't need to
        # persist the run infos during execution in server mode.
        self._flow_executor = FlowExecutor.create(
            flow_file, connections, working_dir, storage=DummyRunStorage(), raise_ex=False
        )

        # Init line execution process pool and set serialize_multimedia_during_execution to True
        # to ensure that images are converted to paths during line execution.
        self._process_pool = LineExecutionProcessPool(
            output_dir,
            self._flow_executor,
            worker_count=worker_count,
            line_timeout_sec=line_timeout_sec,
            serialize_multimedia_during_execution=True,
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
        """Start the process pool."""
        self._process_pool.start()

    async def exec_line(self, request: LineExecutionRequest):
        """Execute a line in the process pool."""
        return await self._process_pool.submit(request.run_id, request.line_number, request.inputs)

    def exec_aggregation(self, request: AggregationRequest):
        """Execute aggregation nodes for the batch run."""
        with self._flow_executor._run_tracker.node_log_manager:
            aggregation_result = self._flow_executor._exec_aggregation(
                request.batch_inputs, request.aggregation_inputs, request.run_id
            )
            # Serialize the multimedia data of the node run infos under the mode artifacts folder.
            for node_run_info in aggregation_result.node_run_infos.values():
                base_dir = self._output_dir / OutputsFolderName.NODE_ARTIFACTS / node_run_info.node
                process_multimedia_in_run_info(node_run_info, base_dir)
        return aggregation_result

    def close(self):
        """Close the process pool."""
        self._process_pool.close()
        self._init = False
        self._instance = None
