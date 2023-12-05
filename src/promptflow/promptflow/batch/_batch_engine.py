# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import asyncio
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from httpx import ConnectError

from promptflow._constants import LINE_NUMBER_KEY, FlowLanguage
from promptflow._core._errors import UnexpectedError
from promptflow._core.operation_context import OperationContext
from promptflow._utils.async_utils import async_run_allowing_running_loop
from promptflow._utils.context_utils import _change_working_dir
from promptflow._utils.execution_utils import (
    apply_default_value_for_input,
    collect_lines,
    get_aggregation_inputs_properties,
    handle_line_failures,
)
from promptflow._utils.logger_utils import bulk_logger
from promptflow._utils.utils import dump_list_to_jsonl, log_progress, resolve_dir_to_absolute, transpose
from promptflow.batch._base_executor_proxy import AbstractExecutorProxy
from promptflow.batch._batch_inputs_processor import BatchInputsProcessor
from promptflow.batch._csharp_executor_proxy import CSharpExecutorProxy
from promptflow.batch._errors import ExecutorServiceUnhealthy
from promptflow.batch._python_executor_proxy import PythonExecutorProxy
from promptflow.batch._result import BatchResult
from promptflow.contracts.flow import Flow
from promptflow.contracts.run_info import Status
from promptflow.exceptions import PromptflowException
from promptflow.executor._result import AggregationResult, LineResult
from promptflow.executor.flow_validator import FlowValidator
from promptflow.storage._run_storage import AbstractRunStorage

OUTPUT_FILE_NAME = "output.jsonl"


class BatchEngine:
    """This class is used to execute flows in batch mode"""

    executor_proxy_classes: Mapping[str, AbstractExecutorProxy] = {
        FlowLanguage.Python: PythonExecutorProxy,
        FlowLanguage.CSharp: CSharpExecutorProxy,
    }

    @classmethod
    def register_executor(cls, type: str, executor_proxy_cls: AbstractExecutorProxy):
        """Register a executor proxy class for a specific program language.

        This method allows users to register a executor proxy class for a particular
        programming language. The executor proxy class will be used when creating an instance
        of the BatchEngine for flows written in the specified language.

        :param type: The flow program language of the executor proxy,
        :type type: str
        :param executor_proxy_cls: The executor proxy class to be registered.
        :type executor_proxy_cls:  ~promptflow.batch.AbstractExecutorProxy
        """
        cls.executor_proxy_classes[type] = executor_proxy_cls

    def __init__(
        self,
        flow_file: Path,
        working_dir: Optional[Path] = None,
        *,
        connections: Optional[dict] = None,
        storage: Optional[AbstractRunStorage] = None,
        **kwargs,
    ):
        """Create a new batch engine instance

        :param flow_file: The flow file path
        :type flow_file: Path
        :param working_dir: The flow working directory path
        :type working_dir: Optional[Path]
        :param connections: The connections used in the flow
        :type connections: Optional[dict]
        :param storage: The storage to store execution results
        :type storage: Optional[~promptflow.storage._run_storage.AbstractRunStorage]
        :param kwargs: The keyword arguments related to creating the executor proxy class
        :type kwargs: Any
        """
        self._working_dir = Flow._resolve_working_dir(flow_file, working_dir)
        self._flow = Flow.from_yaml(flow_file, working_dir=self._working_dir)
        FlowValidator.ensure_flow_valid_in_batch_mode(self._flow)

        executor_proxy_cls = self.executor_proxy_classes[self._flow.program_language]
        with _change_working_dir(self._working_dir):
            self._executor_proxy: AbstractExecutorProxy = executor_proxy_cls.create(
                flow_file, self._working_dir, connections=connections, storage=storage, **kwargs
            )
        self._storage = storage
        # set it to True when the batch run is canceled
        self._is_canceled = False

    def run(
        self,
        input_dirs: Dict[str, str],
        inputs_mapping: Dict[str, str],
        output_dir: Path,
        run_id: Optional[str] = None,
        max_lines_count: Optional[int] = None,
        raise_on_line_failure: Optional[bool] = False,
    ) -> BatchResult:
        """Run flow in batch mode

        :param input_dirs: The directories path of input files
        :type input_dirs: Dict[str, str]
        :param inputs_mapping: The mapping of input names to their corresponding values.
        :type inputs_mapping: Dict[str, str]
        :param output_dir: output dir
        :type output_dir: The directory path of output files
        :param run_id: The run id of this run
        :type run_id: Optional[str]
        :param max_lines_count: The max count of inputs. If it is None, all inputs will be used.
        :type max_lines_count: Optional[int]
        :param raise_on_line_failure: Whether to raise exception when a line fails.
        :type raise_on_line_failure: Optional[bool]
        :return: The result of this batch run
        :rtype: ~promptflow.batch._result.BatchResult
        """

        try:
            self._start_time = datetime.utcnow()
            # set batch input source from input mapping
            OperationContext.get_instance().set_batch_input_source_from_inputs_mapping(inputs_mapping)
            # resolve input data from input dirs and apply inputs mapping
            batch_input_processor = BatchInputsProcessor(self._working_dir, self._flow.inputs, max_lines_count)
            batch_inputs = batch_input_processor.process_batch_inputs(input_dirs, inputs_mapping)
            # resolve output dir
            output_dir = resolve_dir_to_absolute(self._working_dir, output_dir)
            # run flow in batch mode
            with _change_working_dir(self._working_dir):
                return async_run_allowing_running_loop(
                    self._exec_batch, batch_inputs, run_id, output_dir, raise_on_line_failure
                )
        except Exception as e:
            bulk_logger.error(f"Error occurred while executing batch run. Exception: {str(e)}")
            if isinstance(e, ConnectError) or isinstance(e, ExecutorServiceUnhealthy):
                bulk_logger.warning("The batch run may have been canceled or encountered other issues.")
                return BatchResult.create(
                    self._start_time, datetime.utcnow(), [], AggregationResult({}, {}, {}), status=Status.Canceled
                )
            raise e
        finally:
            self._executor_proxy.destroy()

    def cancel(self):
        """Cancel the batch run"""
        self._is_canceled = True

    async def _exec_batch(
        self,
        batch_inputs: List[Dict[str, Any]],
        run_id: str = None,
        output_dir: Path = None,
        raise_on_line_failure: bool = False,
    ) -> BatchResult:
        # apply default value in early stage, so we can use it both in line execution and aggregation nodes execution.
        batch_inputs = [
            apply_default_value_for_input(self._flow.inputs, each_line_input) for each_line_input in batch_inputs
        ]
        run_id = run_id or str(uuid.uuid4())
        if isinstance(self._executor_proxy, PythonExecutorProxy):
            line_results = self._executor_proxy._exec_batch(batch_inputs, output_dir, run_id)
        else:
            line_results = await self._exec_batch_internal(batch_inputs, run_id)
        handle_line_failures([r.run_info for r in line_results], raise_on_line_failure)
        aggr_results = await self._exec_aggregation_internal(batch_inputs, line_results, run_id)

        # persist outputs to output dir
        outputs = [
            {LINE_NUMBER_KEY: r.run_info.index, **r.output}
            for r in line_results
            if r.run_info.status == Status.Completed
        ]
        self._persist_outputs(outputs, output_dir)

        # summary some infos from line results and aggr results to batch result
        self._end_time = datetime.utcnow()
        return BatchResult.create(self._start_time, self._end_time, line_results, aggr_results)

    async def _exec_batch_internal(
        self,
        batch_inputs: List[Mapping[str, Any]],
        run_id: Optional[str] = None,
    ) -> List[LineResult]:
        line_results = []
        total_lines = len(batch_inputs)
        exec_tasks = [self._create_exec_line_task(line_inputs, i, run_id) for i, line_inputs in enumerate(batch_inputs)]
        while len(line_results) < total_lines and not self._is_canceled:
            done, exec_tasks = await asyncio.wait(exec_tasks, return_when=asyncio.FIRST_COMPLETED)
            line_results.extend([task.result() for task in done])
            # log the progress of the batch run
            log_progress(self._start_time, bulk_logger, len(line_results), total_lines)
        if self._is_canceled:
            for task in exec_tasks:
                task.cancel()
        return sorted(line_results, key=lambda r: r.run_info.index)

    def _create_exec_line_task(
        self,
        inputs: Mapping[str, Any],
        index: Optional[int] = None,
        run_id: Optional[str] = None,
    ):
        task = self._executor_proxy.exec_line_async(inputs, index, run_id)
        return asyncio.get_event_loop().create_task(task)

    async def _exec_aggregation_internal(
        self,
        batch_inputs: List[dict],
        line_results: List[LineResult],
        run_id: Optional[str] = None,
    ) -> AggregationResult:
        aggregation_nodes = {node.name for node in self._flow.nodes if node.aggregation}
        if not aggregation_nodes:
            return AggregationResult({}, {}, {})

        bulk_logger.info("Executing aggregation nodes...")

        run_infos = [r.run_info for r in line_results]
        succeeded = [i for i, r in enumerate(run_infos) if r.status == Status.Completed]

        succeeded_batch_inputs = [batch_inputs[i] for i in succeeded]
        resolved_succeeded_batch_inputs = [
            FlowValidator.ensure_flow_inputs_type(flow=self._flow, inputs=input) for input in succeeded_batch_inputs
        ]

        succeeded_inputs = transpose(resolved_succeeded_batch_inputs, keys=list(self._flow.inputs.keys()))

        aggregation_inputs = transpose(
            [result.aggregation_inputs for result in line_results],
            keys=get_aggregation_inputs_properties(self._flow),
        )
        succeeded_aggregation_inputs = collect_lines(succeeded, aggregation_inputs)
        try:
            aggr_results = await self._executor_proxy.exec_aggregation_async(
                succeeded_inputs, succeeded_aggregation_inputs, run_id
            )
            bulk_logger.info("Finish executing aggregation nodes.")
            return aggr_results
        except PromptflowException as e:
            # For PromptflowException, we already do classification, so throw directly.
            raise e
        except Exception as e:
            error_type_and_message = f"({e.__class__.__name__}) {e}"
            raise UnexpectedError(
                message_format=(
                    "Unexpected error occurred while executing the aggregated nodes. "
                    "Please fix or contact support for assistance. The error details: {error_type_and_message}."
                ),
                error_type_and_message=error_type_and_message,
            ) from e

    def _persist_outputs(self, outputs: List[Mapping[str, Any]], output_dir: Path):
        """Persist outputs to json line file in output directory"""
        output_file = output_dir / OUTPUT_FILE_NAME
        dump_list_to_jsonl(output_file, outputs)
