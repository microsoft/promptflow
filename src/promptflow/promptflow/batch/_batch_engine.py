# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import asyncio
import signal
import threading
import uuid
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Type

from promptflow._constants import LANGUAGE_KEY, LINE_NUMBER_KEY, LINE_TIMEOUT_SEC, OUTPUT_FILE_NAME, FlowLanguage
from promptflow._core._errors import ResumeCopyError, UnexpectedError
from promptflow._proxy import ProxyFactory
from promptflow._utils.async_utils import async_run_allowing_running_loop
from promptflow._utils.context_utils import _change_working_dir
from promptflow._utils.execution_utils import (
    apply_default_value_for_input,
    collect_lines,
    extract_aggregation_inputs,
    get_aggregation_inputs_properties,
    handle_line_failures,
    set_batch_input_source_from_inputs_mapping,
)
from promptflow._utils.flow_utils import is_flex_flow
from promptflow._utils.logger_utils import bulk_logger
from promptflow._utils.multimedia_utils import persist_multimedia_data
from promptflow._utils.utils import (
    dump_list_to_jsonl,
    get_int_env_var,
    log_progress,
    resolve_dir_to_absolute,
    transpose,
)
from promptflow._utils.yaml_utils import load_yaml
from promptflow.batch import AbstractExecutorProxy
from promptflow.batch._batch_inputs_processor import BatchInputsProcessor
from promptflow.batch._errors import BatchRunTimeoutError
from promptflow.batch._python_executor_proxy import PythonExecutorProxy
from promptflow.batch._result import BatchResult
from promptflow.contracts.flow import Flow
from promptflow.contracts.run_info import FlowRunInfo, Status
from promptflow.exceptions import ErrorTarget, PromptflowException
from promptflow.executor._line_execution_process_pool import signal_handler
from promptflow.executor._result import AggregationResult, LineResult
from promptflow.executor.flow_validator import FlowValidator
from promptflow.storage import AbstractBatchRunStorage, AbstractRunStorage

DEFAULT_CONCURRENCY = 10


class BatchEngine:
    """This class is used to execute flows in batch mode"""

    @classmethod
    def register_executor(cls, language: str, executor_proxy_cls: Type[AbstractExecutorProxy]):
        """Register a executor proxy class for a specific program language.

        this function is left to keep the compatibility with the old version promptflow-runtime; it will
        redirect the registration to the ExecutorProxyFactory.
        """
        # TODO: remove this after we migrate to multi-container
        ProxyFactory.register_executor(
            language=language,
            executor_proxy_cls=executor_proxy_cls,
        )

    def __init__(
        self,
        flow_file: Path,
        working_dir: Optional[Path] = None,
        *,
        connections: Optional[dict] = None,
        storage: Optional[AbstractRunStorage] = None,
        batch_timeout_sec: Optional[int] = None,
        line_timeout_sec: Optional[int] = None,
        worker_count: Optional[int] = None,
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
        :param batch_timeout: The timeout of batch run in seconds
        :type batch_timeout: Optional[int]
        :param line_timeout: The timeout of each line in seconds
        :type line_timeout: Optional[int]
        :param worker_count: The concurrency limit of batch run
        :type worker_count: Optional[int]
        :param kwargs: The keyword arguments related to creating the executor proxy class
        :type kwargs: Any
        """
        self._flow_file = flow_file
        self._working_dir = Flow._resolve_working_dir(flow_file, working_dir)

        self._is_eager_flow, self._program_language = self._check_eager_flow_and_language_from_yaml()

        # TODO: why self._flow is not initialized for eager flow?
        if not self._is_eager_flow:
            self._flow = Flow.from_yaml(flow_file, working_dir=self._working_dir)
            FlowValidator.ensure_flow_valid_in_batch_mode(self._flow)

        self._connections = connections
        self._storage = storage
        self._kwargs = kwargs

        self._batch_timeout_sec = batch_timeout_sec or get_int_env_var("PF_BATCH_TIMEOUT_SEC")
        self._line_timeout_sec = line_timeout_sec or get_int_env_var("PF_LINE_TIMEOUT_SEC", LINE_TIMEOUT_SEC)
        self._worker_count = worker_count or get_int_env_var("PF_WORKER_COUNT")
        # update kwargs with worker_count and line_timeout_sec
        self._kwargs.update(
            {
                "worker_count": self._worker_count,
                "line_timeout_sec": self._line_timeout_sec,
            }
        )

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
        resume_from_run_storage: Optional[AbstractBatchRunStorage] = None,
        resume_from_run_output_dir: Optional[Path] = None,
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
        :param resume_from_run_storage: The run storage to load flow run and node run from the original
                                        run. The resume behavior is to reuse succeeded line result of
                                        the original run and run/rerun the remaining/failed lines.
        :type resume_from_run_storage: Optional[AbstractRunStorage]
        :param resume_from_run_output_dir: The output dir of the original run.
        :type resume_from_run_output_dir: Optional[Path]
        :return: The result of this batch run
        :rtype: ~promptflow.batch._result.BatchResult
        """
        try:
            self._start_time = datetime.utcnow()
            with _change_working_dir(self._working_dir):
                # create executor proxy instance according to the flow program language
                self._executor_proxy = ProxyFactory().create_executor_proxy(
                    flow_file=self._flow_file,
                    working_dir=self._working_dir,
                    connections=self._connections,
                    storage=self._storage,
                    language=self._program_language,
                    **self._kwargs,
                )
                try:
                    # register signal handler for python flow in the main thread
                    # TODO: For all executor proxies that are executed locally, it might be necessary to
                    #  register a signal for Ctrl+C in order to customize some actions beyond just killing
                    #  the process, such as terminating the executor service.
                    if isinstance(self._executor_proxy, PythonExecutorProxy):
                        if threading.current_thread() is threading.main_thread():
                            signal.signal(signal.SIGINT, signal_handler)
                        else:
                            bulk_logger.info(
                                "Current thread is not main thread, skip signal handler registration in BatchEngine."
                            )

                    # set batch input source from input mapping
                    set_batch_input_source_from_inputs_mapping(inputs_mapping)
                    # if using eager flow, the self._flow is none, so we need to get inputs definition from executor
                    inputs = self._executor_proxy.get_inputs_definition() if self._is_eager_flow else self._flow.inputs
                    # resolve input data from input dirs and apply inputs mapping
                    batch_input_processor = BatchInputsProcessor(self._working_dir, inputs, max_lines_count)
                    batch_inputs = batch_input_processor.process_batch_inputs(input_dirs, inputs_mapping)
                    # resolve output dir
                    output_dir = resolve_dir_to_absolute(self._working_dir, output_dir)

                    run_id = run_id or str(uuid.uuid4())

                    previous_run_results = None
                    if resume_from_run_storage and resume_from_run_output_dir:
                        previous_run_results = self._copy_previous_run_result(
                            resume_from_run_storage, resume_from_run_output_dir, batch_inputs, output_dir, run_id
                        )

                    # run flow in batch mode
                    return async_run_allowing_running_loop(
                        self._exec_in_task,
                        batch_inputs,
                        run_id,
                        output_dir,
                        raise_on_line_failure,
                        previous_run_results,
                    )
                finally:
                    async_run_allowing_running_loop(self._executor_proxy.destroy)
        except Exception as e:
            bulk_logger.error(f"Error occurred while executing batch run. Exception: {str(e)}")
            if isinstance(e, PromptflowException):
                raise e
            else:
                # for unexpected error, we need to wrap it to SystemErrorException to allow us to see the stack trace.
                unexpected_error = UnexpectedError(
                    target=ErrorTarget.BATCH,
                    message_format=(
                        "Unexpected error occurred while executing the batch run. Error: {error_type_and_message}."
                    ),
                    error_type_and_message=f"({e.__class__.__name__}) {e}",
                )
                raise unexpected_error from e

    def _copy_previous_run_result(
        self,
        resume_from_run_storage: AbstractBatchRunStorage,
        resume_from_run_output_dir: Path,
        batch_inputs: List,
        output_dir: Path,
        run_id: str,
    ) -> List[LineResult]:
        """Duplicate the previous debug_info from resume_from_run_storage and output from resume_from_run_output_dir
        to the storage of new run,
        return the list of previous line results for the usage of aggregation and summarization.
        """
        try:
            previous_run_results = []
            for i in range(len(batch_inputs)):
                previous_run_info: FlowRunInfo = resume_from_run_storage.load_flow_run_info(i)

                if previous_run_info and previous_run_info.status == Status.Completed:
                    # UI uses root_run_id  to link the base path in datastore with the run_info of line.
                    # Thus the root_run_id needs to be the current batch run id.
                    previous_run_info.root_run_id = run_id
                    previous_run_info.parent_run_id = run_id
                    # Load previous node run info
                    previous_node_run_infos = resume_from_run_storage.load_node_run_info_for_line(i)
                    previous_node_run_infos_dict = {node_run.node: node_run for node_run in previous_node_run_infos}
                    previous_node_run_outputs = {
                        node_info.node: node_info.output for node_info in previous_node_run_infos
                    }

                    # Extract aggregation inputs for flow with aggregation node
                    aggregation_inputs = extract_aggregation_inputs(self._flow, previous_node_run_outputs)

                    # Deepcopy to avoid modifying the original object when serializing image
                    previous_run_output = deepcopy(previous_run_info.output)
                    previous_run_output_in_line_result = persist_multimedia_data(previous_run_output, output_dir)

                    # Persist previous run info and node run info
                    self._storage.persist_flow_run(previous_run_info)
                    for node_run_info in previous_node_run_infos:
                        self._storage.persist_node_run(node_run_info)

                    # Create LineResult object for previous line result
                    previous_line_result = LineResult(
                        output=previous_run_output_in_line_result,
                        aggregation_inputs=aggregation_inputs,
                        run_info=previous_run_info,
                        node_run_infos=previous_node_run_infos_dict,
                    )
                    previous_run_results.append(previous_line_result)

            return previous_run_results
        except Exception as e:
            bulk_logger.error(f"Error occurred while copying previous run result. Exception: {str(e)}")
            resume_copy_error = ResumeCopyError(
                target=ErrorTarget.BATCH,
                message_format="Failed to copy results when resuming the run. Error: {error_type_and_message}.",
                error_type_and_message=f"({e.__class__.__name__}) {e}",
            )
            raise resume_copy_error from e

    def cancel(self):
        """Cancel the batch run"""
        self._is_canceled = True

    async def _exec_in_task(
        self,
        batch_inputs: List[Dict[str, Any]],
        run_id: str = None,
        output_dir: Path = None,
        raise_on_line_failure: bool = False,
        previous_line_results: List[LineResult] = None,
    ) -> BatchResult:
        # if the batch run is canceled, asyncio.CancelledError will be raised and no results will be returned,
        # so we pass empty line results list and aggr results and update them in _exec so that when the batch
        # run is canceled we can get the current completed line results and aggr results.
        line_results: List[LineResult] = []
        aggr_result = AggregationResult({}, {}, {})
        task = asyncio.create_task(
            self._exec(
                batch_inputs,
                run_id,
                output_dir,
                raise_on_line_failure,
                previous_line_results,
                line_results,
                aggr_result,
            )
        )
        while not task.done():
            # check whether the task is completed or canceled every 1s
            await asyncio.sleep(1)
            if self._is_canceled:
                task.cancel()
                # use current completed line results and aggregation results to create a BatchResult
                return BatchResult.create(
                    self._start_time, datetime.utcnow(), line_results, aggr_result, status=Status.Canceled
                )
        return task.result()

    async def _exec(
        self,
        batch_inputs: List[Dict[str, Any]],
        run_id: str = None,
        output_dir: Path = None,
        raise_on_line_failure: bool = False,
        previous_line_results: List[LineResult] = None,
        line_results: List[LineResult] = [],
        aggr_result: AggregationResult = AggregationResult({}, {}, {}),
    ) -> BatchResult:
        """
        Asynchronously execute batch processing of inputs with potential resumption from previous results,
        and aggregate outputs accordingly. Empty list `line_results` and `aggr_result` is passed to ensure
        their current state can be retrieved when batch run is canceled.

        :param batch_inputs: A list of dictionaries representing the inputs for all lines of the batch.
        :type batch_inputs: List[Mapping[str, Any]]
        :param run_id: An optional unique identifier for the run. If not provided, a new UUID will be generated.
        :type run_id: Optional[str]
        :param output_dir: An optional path to a directory where outputs will be persisted.
        :type output_dir: Optional[Path]
        :param raise_on_line_failure: A flag indicating whether to raise an exception on individual line failures.
        :type raise_on_line_failure: bool
        :param previous_line_results: An optional list of previous line results to resume from.
        :type previous_line_results: Optional[List[~promptflow.executor._result.LineResult]]
        :param line_results: An output parameter to be populated with the results of processing all lines in the batch.
        :type line_results: List[~promptflow.executor._result.LineResult]
        :param aggr_result: An output parameter to be populated with the aggregated results of all lines in the batch.
        :type aggr_result: ~promptflow.executor._result.AggregationResult
        :return: A `BatchResult` object containing information about the execution of the batch.
        :rtype: ~promptflow.batch._result.BatchResult
        """
        # ensure executor health before execution
        await self._executor_proxy.ensure_executor_health()
        # apply default value in early stage, so we can use it both in line and aggregation nodes execution.
        # if the flow is None, we don't need to apply default value for inputs.
        if not self._is_eager_flow:
            batch_inputs = [
                apply_default_value_for_input(self._flow.inputs, each_line_input) for each_line_input in batch_inputs
            ]

        # if there are existing results resumed from previous run, we should skip the execution of these lines
        if previous_line_results:
            line_results.extend(previous_line_results)
            existing_results_line_numbers = set([r.run_info.index for r in previous_line_results])
            bulk_logger.info(f"Skipped the execution of {len(existing_results_line_numbers)} existing results.")
            inputs_to_run = [
                input for input in batch_inputs if input[LINE_NUMBER_KEY] not in existing_results_line_numbers
            ]
        else:
            inputs_to_run = batch_inputs

        run_id = run_id or str(uuid.uuid4())

        # execute lines
        is_timeout = False
        if isinstance(self._executor_proxy, PythonExecutorProxy):
            results, is_timeout = await self._executor_proxy._exec_batch(
                inputs_to_run,
                output_dir,
                run_id,
                batch_timeout_sec=self._batch_timeout_sec,
                line_timeout_sec=self._line_timeout_sec,
                worker_count=self._worker_count,
            )
            line_results.extend(results)
        else:
            # TODO: Enable batch timeout for other api based executor proxy
            await self._exec_batch(line_results, batch_inputs, run_id)
        handle_line_failures([r.run_info for r in line_results], raise_on_line_failure)
        # persist outputs to output dir
        outputs = [
            {LINE_NUMBER_KEY: r.run_info.index, **r.output}
            for r in line_results
            if r.run_info.status == Status.Completed
        ]
        outputs.sort(key=lambda x: x[LINE_NUMBER_KEY])
        self._persist_outputs(outputs, output_dir)

        # if the batch runs with errors, we should update the errors to ex
        ex = None
        if not is_timeout:
            # execute aggregation nodes
            aggr_exec_result = await self._exec_aggregation(batch_inputs, line_results, run_id)
            # use the execution result to update aggr_result to make sure we can get the aggr_result in _exec_in_task
            self._update_aggr_result(aggr_result, aggr_exec_result)
        else:
            ex = BatchRunTimeoutError(
                message="The batch run failed due to timeout. Please adjust the timeout settings to a higher value.",
                target=ErrorTarget.BATCH,
            )
        # summary some infos from line results and aggr results to batch result
        return BatchResult.create(self._start_time, datetime.utcnow(), line_results, aggr_result, exception=ex)

    async def _exec_batch(
        self,
        line_results: List[LineResult],
        batch_inputs: List[Mapping[str, Any]],
        run_id: Optional[str] = None,
    ) -> List[LineResult]:
        worker_count = self._worker_count or DEFAULT_CONCURRENCY
        semaphore = asyncio.Semaphore(worker_count)
        pending = [
            asyncio.create_task(self._exec_line_under_semaphore(semaphore, line_inputs, i, run_id))
            for i, line_inputs in enumerate(batch_inputs)
        ]

        total_lines = len(batch_inputs)
        completed_line = 0
        while completed_line < total_lines:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            completed_line_results = [task.result() for task in done]
            self._persist_run_info(completed_line_results)
            line_results.extend(completed_line_results)
            log_progress(
                self._start_time,
                bulk_logger,
                len(line_results),
                total_lines,
                last_log_count=completed_line,
            )
            completed_line = len(line_results)

    async def _exec_line_under_semaphore(
        self,
        semaphore,
        inputs: Mapping[str, Any],
        index: Optional[int] = None,
        run_id: Optional[str] = None,
    ):
        async with semaphore:
            return await self._executor_proxy.exec_line_async(inputs, index, run_id)

    async def _exec_aggregation(
        self,
        batch_inputs: List[dict],
        line_results: List[LineResult],
        run_id: Optional[str] = None,
    ) -> AggregationResult:
        if self._is_eager_flow:
            return AggregationResult({}, {}, {})
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
            aggr_result = await self._executor_proxy.exec_aggregation_async(
                succeeded_inputs, succeeded_aggregation_inputs, run_id
            )
            # if the flow language is python, we have already persisted node run infos during execution.
            # so we should persist node run infos in aggr_result for other languages.
            if not isinstance(self._executor_proxy, PythonExecutorProxy):
                for node_run in aggr_result.node_run_infos.values():
                    self._storage.persist_node_run(node_run)
            bulk_logger.info("Finish executing aggregation nodes.")
            return aggr_result
        except PromptflowException as e:
            # for PromptflowException, we already do classification, so throw directly.
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

    def _persist_run_info(self, line_results: List[LineResult]):
        """Persist node run infos and flow run info in line result to storage"""
        for line_result in line_results:
            for node_run in line_result.node_run_infos.values():
                self._storage.persist_node_run(node_run)
            self._storage.persist_flow_run(line_result.run_info)

    def _persist_outputs(self, outputs: List[Mapping[str, Any]], output_dir: Path):
        """Persist outputs to json line file in output directory"""
        output_file = output_dir / OUTPUT_FILE_NAME
        dump_list_to_jsonl(output_file, outputs)

    def _update_aggr_result(self, aggr_result: AggregationResult, aggr_exec_result: AggregationResult):
        """Update aggregation result with the aggregation execution result"""
        aggr_result.metrics = aggr_exec_result.metrics
        aggr_result.node_run_infos = aggr_exec_result.node_run_infos
        aggr_result.output = aggr_exec_result.output

    def _check_eager_flow_and_language_from_yaml(self):
        flow_file = self._working_dir / self._flow_file if self._working_dir else self._flow_file
        # TODO: remove this after path is removed
        if flow_file.suffix.lower() == ".dll":
            return True, FlowLanguage.CSharp
        with open(flow_file, "r", encoding="utf-8") as fin:
            flow_dag = load_yaml(fin)
        language = flow_dag.get(LANGUAGE_KEY, FlowLanguage.Python)
        return is_flex_flow(yaml_dict=flow_dag), language
