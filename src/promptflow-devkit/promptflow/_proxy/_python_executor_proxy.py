# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from promptflow._constants import FlowEntryRegex
from promptflow._core._errors import UnexpectedError
from promptflow._core.run_tracker import RunTracker
from promptflow._sdk._constants import FLOW_META_JSON_GEN_TIMEOUT, FLOW_TOOLS_JSON_GEN_TIMEOUT
from promptflow._sdk._utilities.general_utils import can_accept_kwargs
from promptflow._utils.flow_utils import resolve_python_entry_file
from promptflow._utils.logger_utils import bulk_logger
from promptflow._utils.yaml_utils import load_yaml
from promptflow.contracts.run_mode import RunMode
from promptflow.executor import FlowExecutor
from promptflow.executor._line_execution_process_pool import LineExecutionProcessPool
from promptflow.executor._result import AggregationResult, LineResult
from promptflow.executor._script_executor import ScriptExecutor
from promptflow.storage._run_storage import AbstractRunStorage
from promptflow.tracing._operation_context import OperationContext

from ._base_executor_proxy import AbstractExecutorProxy


class PythonExecutorProxy(AbstractExecutorProxy):
    def __init__(self, flow_executor: FlowExecutor):
        super().__init__()
        self._flow_executor = flow_executor

    @classmethod
    def _generate_flow_json(
        cls,
        flow_file: Path,
        working_dir: Path,
        dump: bool = True,
        timeout: int = FLOW_META_JSON_GEN_TIMEOUT,
        load_in_subprocess: bool = True,
    ) -> Dict[str, Any]:
        from promptflow._core.entry_meta_generator import generate_flow_meta

        flow_dag = load_yaml(flow_file)
        # generate flow.json only for eager flow for now
        return generate_flow_meta(
            flow_directory=working_dir,
            source_path=resolve_python_entry_file(entry=flow_dag.get("entry"), working_dir=working_dir),
            data=flow_dag,
            dump=dump,
            timeout=timeout,
            load_in_subprocess=load_in_subprocess,
        )

    @classmethod
    async def create(
        cls,
        flow_file: Path,
        working_dir: Optional[Path] = None,
        *,
        connections: Optional[dict] = None,
        storage: Optional[AbstractRunStorage] = None,
        init_kwargs: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> "PythonExecutorProxy":
        # Check if the method accepts kwargs in case of customer using an outdated version of core package.
        if can_accept_kwargs(FlowExecutor.create):
            flow_executor = FlowExecutor.create(
                flow_file, connections, working_dir, storage=storage, raise_ex=False, init_kwargs=init_kwargs, **kwargs
            )
        else:
            flow_executor = FlowExecutor.create(
                flow_file, connections, working_dir, storage=storage, raise_ex=False, init_kwargs=init_kwargs
            )
        return cls(flow_executor)

    @property
    def has_aggregation(self) -> bool:
        return self._flow_executor.has_aggregation_node

    async def exec_aggregation_async(
        self,
        batch_inputs: Mapping[str, Any],
        aggregation_inputs: Mapping[str, Any],
        run_id: Optional[str] = None,
    ) -> AggregationResult:
        return self._flow_executor.exec_aggregation(batch_inputs, aggregation_inputs, run_id=run_id)

    async def exec_line_async(
        self,
        inputs: Mapping[str, Any],
        index: Optional[int] = None,
        run_id: Optional[str] = None,
    ) -> LineResult:
        return await self._flow_executor.exec_line_async(inputs, index, run_id)

    async def _exec_batch(
        self,
        batch_inputs: List[Mapping[str, Any]],
        output_dir: Path,
        run_id: Optional[str] = None,
        batch_timeout_sec: Optional[int] = None,
        line_timeout_sec: Optional[int] = None,
        worker_count: Optional[int] = None,
    ) -> Tuple[List[LineResult], bool]:
        # TODO: Refine the logic here since the script executor actually doesn't have the 'node' concept
        if isinstance(self._flow_executor, ScriptExecutor):
            run_tracker = RunTracker(self._flow_executor._storage)
        else:
            run_tracker = self._flow_executor._run_tracker

        with run_tracker.node_log_manager:
            OperationContext.get_instance().run_mode = RunMode.Batch.name
            if self._flow_executor._flow_file is None:
                raise UnexpectedError(
                    "Unexpected error occurred while init FlowExecutor. Error details: flow file is missing."
                )

            if batch_timeout_sec:
                bulk_logger.info(f"The timeout for the batch run is {batch_timeout_sec} seconds.")

            with LineExecutionProcessPool(
                output_dir,
                self._flow_executor,
                worker_count=worker_count,
                line_timeout_sec=line_timeout_sec,
                batch_timeout_sec=batch_timeout_sec,
                run_id=run_id,
                nlines=len(batch_inputs),
            ) as pool:
                line_number = [batch_input["line_number"] for batch_input in batch_inputs]
                line_results = await pool.run(zip(line_number, batch_inputs))

            # For bulk run, currently we need to add line results to run_tracker
            self._flow_executor._add_line_results(line_results, run_tracker)
        return line_results, pool.is_timeout

    def get_inputs_definition(self):
        return self._flow_executor.get_inputs_definition()

    @classmethod
    def _generate_flow_tools_json(
        cls,
        flow_file: Path,
        working_dir: Path,
        dump: bool = True,
        timeout: int = FLOW_TOOLS_JSON_GEN_TIMEOUT,
        load_in_subprocess: bool = True,
    ) -> dict:
        from promptflow._sdk._utilities.general_utils import generate_flow_tools_json

        return generate_flow_tools_json(
            flow_directory=working_dir,
            dump=dump,
            timeout=timeout,
            used_packages_only=True,
        )

    @classmethod
    def is_flex_flow_entry(cls, entry: str):
        """Returns True if entry is flex flow's entry (in python)."""
        return bool(isinstance(entry, str) and re.match(FlowEntryRegex.Python, entry))
