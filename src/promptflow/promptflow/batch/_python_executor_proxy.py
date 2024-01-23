# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from pathlib import Path
from typing import Any, List, Mapping, Optional

from promptflow._constants import LINE_TIMEOUT_SEC
from promptflow._core._errors import UnexpectedError
from promptflow._core.operation_context import OperationContext
from promptflow.batch._base_executor_proxy import AbstractExecutorProxy
from promptflow.contracts.run_mode import RunMode
from promptflow.executor import FlowExecutor
from promptflow.executor._flow_nodes_scheduler import DEFAULT_CONCURRENCY_BULK
from promptflow.executor._line_execution_process_pool import LineExecutionProcessPool
from promptflow.executor._result import AggregationResult, LineResult
from promptflow.storage._run_storage import AbstractRunStorage


class PythonExecutorProxy(AbstractExecutorProxy):
    def __init__(self, flow_executor: FlowExecutor):
        self._flow_executor = flow_executor

    @classmethod
    async def create(
        cls,
        flow_file: Path,
        working_dir: Optional[Path] = None,
        *,
        connections: Optional[dict] = None,
        storage: Optional[AbstractRunStorage] = None,
        **kwargs,
    ) -> "PythonExecutorProxy":
        line_timeout_sec = kwargs.get("line_timeout_sec", LINE_TIMEOUT_SEC)
        flow_executor = FlowExecutor.create(
            flow_file,
            connections,
            working_dir,
            storage=storage,
            raise_ex=False,
            line_timeout_sec=line_timeout_sec,
        )
        return cls(flow_executor)

    async def exec_aggregation_async(
        self,
        batch_inputs: Mapping[str, Any],
        aggregation_inputs: Mapping[str, Any],
        run_id: Optional[str] = None,
    ) -> AggregationResult:
        with self._flow_executor._run_tracker.node_log_manager:
            return self._flow_executor._exec_aggregation(batch_inputs, aggregation_inputs, run_id=run_id)

    def _exec_batch(
        self,
        batch_inputs: List[Mapping[str, Any]],
        output_dir: Path,
        run_id: Optional[str] = None,
        batch_timeout_sec: Optional[int] = None,
    ) -> List[LineResult]:
        self._flow_executor._node_concurrency = DEFAULT_CONCURRENCY_BULK
        with self._flow_executor._run_tracker.node_log_manager:
            OperationContext.get_instance().run_mode = RunMode.Batch.name
            line_results = self._exec_batch_with_process_pool(
                batch_inputs, output_dir, run_id, batch_timeout_sec=batch_timeout_sec
            )
            # For bulk run, currently we need to add line results to run_tracker
            self._flow_executor._add_line_results(line_results)
        return line_results

    def _exec_batch_with_process_pool(
        self,
        batch_inputs: List[Mapping[str, Any]],
        output_dir: Path,
        run_id: Optional[str] = None,
        batch_timeout_sec: Optional[int] = None,
    ) -> List[LineResult]:
        nlines = len(batch_inputs)
        line_number = [batch_input["line_number"] for batch_input in batch_inputs]

        if self._flow_executor._flow_file is None:
            raise UnexpectedError(
                "Unexpected error occurred while init FlowExecutor. Error details: flow file is missing."
            )

        with LineExecutionProcessPool(
            self._flow_executor,
            nlines,
            run_id,
            output_dir,
            batch_timeout_sec=batch_timeout_sec,
        ) as pool:
            return pool.run(zip(line_number, batch_inputs))

    @classmethod
    def _get_tool_metadata(cls, flow_file: Path, working_dir: Path) -> dict:
        from promptflow._sdk._utils import generate_flow_tools_json

        return generate_flow_tools_json(
            flow_directory=working_dir,
            dump=False,
            used_packages_only=True,
        )
