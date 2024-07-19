# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import asyncio
import inspect
import signal
import threading
import uuid
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Type, Union

from promptflow._constants import (
    LANGUAGE_KEY,
    LINE_NUMBER_KEY,
    LINE_TIMEOUT_SEC,
    OUTPUT_FILE_NAME,
    FlowLanguage,
    MessageFormatType,
)
from promptflow._core._errors import ResumeCopyError, UnexpectedError
from promptflow._proxy import AbstractExecutorProxy, ProxyFactory
from promptflow._proxy._python_executor_proxy import PythonExecutorProxy
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
from promptflow._utils.flow_utils import is_flex_flow, is_prompty_flow
from promptflow._utils.logger_utils import bulk_logger
from promptflow._utils.multimedia_utils import MultimediaProcessor
from promptflow._utils.utils import (
    dump_list_to_jsonl,
    get_int_env_var,
    log_progress,
    resolve_dir_to_absolute,
    transpose,
)
from promptflow._utils.yaml_utils import load_yaml
from promptflow.batch._batch_inputs_processor import BatchInputsProcessor
from promptflow.batch._errors import BatchRunTimeoutError
from promptflow.batch._result import BatchResult
from promptflow.contracts.flow import Flow
from promptflow.contracts.run_info import FlowRunInfo, Status
from promptflow.contracts.types import AttrDict
from promptflow.exceptions import ErrorTarget, PromptflowException
from promptflow.executor._line_execution_process_pool import signal_handler
from promptflow.executor._result import AggregationResult, LineResult
from promptflow.executor.flow_validator import FlowValidator
from promptflow.storage import AbstractBatchRunStorage, AbstractRunStorage
from promptflow.storage._run_storage import DefaultRunStorage

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
        flow_file: Union[Path, Callable],
        working_dir: Optional[Path] = None,
        *,
        connections: Optional[dict] = None,
        storage: Optional[AbstractRunStorage] = None,
        batch_timeout_sec: Optional[int] = None,
        line_timeout_sec: Optional[int] = None,
        worker_count: Optional[int] = None,
        init_kwargs: Optional[Dict[str, Any]] = None,
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
        :param init_kwargs: Class init arguments for callable class, only supported for flex flow.
        :type init_kwargs: Optional[Dict[str, Any]]
        :param kwargs: The keyword arguments related to creating the executor proxy class
        :type kwargs: Any
        """
        self._flow_file = flow_file
        is_function_entry = hasattr(flow_file, "__call__") or inspect.isfunction(flow_file)
        if is_function_entry:
            self._working_dir = working_dir or Path.cwd()
        else:
            self._working_dir = (
                Flow._resolve_working_dir(flow_file, working_dir) if flow_file is not None else working_dir
            )

        # Chat group doesn't pass flow_file
        if self._flow_file is not None:
            if is_function_entry:
                self._is_eager_flow = True
                self._program_language = FlowLanguage.Python
            elif is_prompty_flow(self._flow_file):
                self._is_eager_flow = True
                self._program_language = FlowLanguage.Python
            else:
                self._is_prompty_flow = False
                self._is_eager_flow, self._program_language = self._check_eager_flow_and_language_from_yaml()
        else:
            self._is_prompty_flow = False
            self._is_eager_flow = False
            self._program_language = None

        # TODO: why self._flow is not initialized for eager flow?
        # Chat group run does not pass flow_file
        if flow_file is not None and not self._is_eager_flow:
            self._flow = Flow.from_yaml(flow_file, working_dir=self._working_dir)
            FlowValidator.ensure_flow_valid_in_batch_mode(self._flow)

        # eager flow and chat group does not support multimedia contract currently, just use basic format type.
        if not self._is_eager_flow and self._flow_file is not None:
            self._message_format = self._flow.message_format
        else:
            self._message_format = MessageFormatType.BASIC
        self._multimedia_processor = MultimediaProcessor.create(self._message_format)

        self._connections = connections
        self._storage = storage if storage else DefaultRunStorage(base_dir=self._working_dir)
        self._kwargs = kwargs

        self._batch_use_async = kwargs.get("batch_use_async", False)
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
        self._init_kwargs = init_kwargs

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
        executor_proxy: Optional[AbstractExecutorProxy] = None,
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
                self._executor_proxy = executor_proxy or ProxyFactory().create_executor_proxy(
                    flow_file=self._flow_file,
                    working_dir=self._working_dir,
                    connections=self._connections,
                    storage=self._storage,
                    language=self._program_language,
                    init_kwargs=self._init_kwargs,
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

                    if self._executor_proxy.should_apply_inputs_mapping:
                        # set batch input source from input mapping
                        set_batch_input_source_from_inputs_mapping(inputs_mapping)
                        # if using eager flow, the self._flow is none, so we need to get inputs definition from executor
                        inputs = (
                            self._executor_proxy.get_inputs_definition() if self._is_eager_flow else self._flow.inputs
                        )

                        # resolve input data from input dirs and apply inputs mapping
                        batch_input_processor = BatchInputsProcessor(
                            self._working_dir, inputs, max_lines_count, message_format=self._message_format
                        )
                        batch_inputs = batch_input_processor.process_batch_inputs(input_dirs, inputs_mapping)
                    else:
                        batch_input_processor = BatchInputsProcessor("", {}, max_lines_count)
                        batch_inputs = batch_input_processor.process_batch_inputs_without_inputs_mapping(input_dirs)
                    # resolve output dir
                    output_dir = resolve_dir_to_absolute(self._working_dir, output_dir)

                    run_id = run_id or str(uuid.uuid4())
                    previous_run_results = None
                    if resume_from_run_storage:
                        previous_run_results = self._copy_previous_run_result(
                            resume_from_run_storage, batch_inputs, output_dir, run_id
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
        batch_inputs: List,
        output_dir: Path,
        run_id: str,
    ) -> List[LineResult]:
        """Duplicate the previous debug_info from resume_from_run_storage to the storage of new run,
        return the list of previous line results for the usage of aggregation and summarization.
        """
        try:
            previous_run_results = []
            if not self._is_eager_flow:
                aggregation_nodes = {node.name for node in self._flow.nodes if node.aggregation}
            for i, _ in enumerate(batch_inputs):
                previous_run_info: FlowRunInfo = resume_from_run_storage.load_flow_run_info(i)

                if not previous_run_info or previous_run_info.status != Status.Completed:
                    continue

                # UI uses root_run_id  to link the base path in datastore with the run_info of line.
                # Thus the root_run_id needs to be the current batch run id.
                previous_run_info.root_run_id = run_id
                previous_run_info.parent_run_id = run_id

                # Deepcopy to avoid modifying the original object when serializing image
                self._storage.persist_flow_run(previous_run_info)
                previous_run_output = deepcopy(previous_run_info.output)
                previous_run_output_in_line_result = self._multimedia_processor.persist_multimedia_data(
                    previous_run_output, output_dir
                )

                if self._is_eager_flow:
                    # Directly create LineResult object for previous line result
                    previous_line_result = LineResult(
                        output=previous_run_output_in_line_result,
                        aggregation_inputs=previous_run_output_in_line_result,
                        run_info=previous_run_info,
                        node_run_infos={},
                    )
                else:
                    # Since there is no node run in flex flow, only load previous node run info when it is not flex flow
                    previous_node_run_infos = resume_from_run_storage.load_node_run_info_for_line(i)
                    # In storage, aggregation nodes are persisted with filenames similar to regular nodes.
                    # Currently we read regular node run records by filename in the node artifacts folder,
                    # which may lead to load records of aggregation nodes at the same time, which is not intended.
                    # E.g, aggregation-node/000000000.jsonl will be treated as the node_run_info of the first line:
                    # node_artifacts/
                    # ├─ non-aggregation-node/
                    # │  ├─ 000000000.jsonl
                    # │  ├─ 000000001.jsonl
                    # │  ├─ 000000002.jsonl
                    # ├─ aggregation-node/
                    # │  ├─ 000000000.jsonl
                    # So we filter out aggregation nodes since line records should not contain any info about them.
                    previous_node_run_infos = [
                        run_info for run_info in previous_node_run_infos if run_info.node not in aggregation_nodes
                    ]
                    previous_node_run_infos_dict = {node_run.node: node_run for node_run in previous_node_run_infos}
                    previous_node_run_outputs = {
                        node_info.node: node_info.output for node_info in previous_node_run_infos
                    }
                    # Extract aggregation inputs for flow with aggregation node
                    aggregation_inputs = extract_aggregation_inputs(self._flow, previous_node_run_outputs)

                    # Persist node run info to storage
                    for node_run_info in previous_node_run_infos:
                        self._storage.persist_node_run(node_run_info)

                    # Create LineResult object with aggregation inputs and node_run_infos
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
            raise ResumeCopyError(
                target=ErrorTarget.BATCH,
                message_format="Failed to copy results when resuming the run. Error: {error_type_and_message}.",
                error_type_and_message=f"({e.__class__.__name__}) {e}",
            ) from e

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
            if self._batch_timeout_expired():
                task.cancel()
                ex = BatchRunTimeoutError(
                    message_format=(
                        "The batch run failed due to timeout [{batch_timeout_sec}s]. "
                        "Please adjust the timeout to a higher value."
                    ),
                    batch_timeout_sec=self._batch_timeout_sec,
                    target=ErrorTarget.BATCH,
                )
                # summary some infos from line results and aggr results to batch result
                return BatchResult.create(self._start_time, datetime.utcnow(), line_results, aggr_result, exception=ex)
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
        if not self._is_eager_flow and self._flow_file is not None:
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
        if not self._batch_use_async and isinstance(self._executor_proxy, PythonExecutorProxy):
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
            await self._exec_batch(line_results, inputs_to_run, run_id)

        handle_line_failures([r.run_info for r in line_results], raise_on_line_failure)
        # Flex flow may return primitive types as output, so we need to wrap them in a dictionary.
        outputs = [
            {LINE_NUMBER_KEY: r.run_info.index, **r.output}
            if isinstance(r.output, dict)
            else {LINE_NUMBER_KEY: r.run_info.index, "output": r.output}
            for r in line_results
            if r.run_info.status == Status.Completed
        ]
        # persist outputs to output dir
        outputs.sort(key=lambda x: x[LINE_NUMBER_KEY])
        self._persist_outputs(outputs, output_dir)

        # if the batch runs with errors, we should update the errors to ex
        ex = None
        if is_timeout:
            ex = BatchRunTimeoutError(
                message_format=(
                    "The batch run failed due to timeout [{batch_timeout_sec}s]. "
                    "Please adjust the timeout to a higher value."
                ),
                batch_timeout_sec=self._batch_timeout_sec,
                target=ErrorTarget.BATCH,
            )
        elif self._executor_proxy.allow_aggregation:
            # execute aggregation nodes
            aggr_exec_result = await self._exec_aggregation(batch_inputs, line_results, run_id)
            # use the execution result to update aggr_result to make sure we can get the aggr_result in _exec_in_task
            self._update_aggr_result(aggr_result, aggr_exec_result)
        # summary some infos from line results and aggr results to batch result
        return BatchResult.create(self._start_time, datetime.utcnow(), line_results, aggr_result, exception=ex)

    async def _exec_batch(
        self,
        line_results: List[LineResult],
        batch_inputs: List[Mapping[str, Any]],
        run_id: Optional[str] = None,
    ) -> List[LineResult]:
        # line_results as input parameter, so that the completed line results can be summarized
        # when batch run is canceled.
        worker_count = self._worker_count or DEFAULT_CONCURRENCY
        semaphore = asyncio.Semaphore(worker_count)

        pending = [
            asyncio.create_task(
                self._exec_line_under_semaphore(semaphore, line_input, line_input[LINE_NUMBER_KEY], run_id)
            )
            for line_input in batch_inputs
        ]

        total_lines = len(batch_inputs)
        completed_line = 0
        last_log_count = 0
        while completed_line < total_lines:
            # wait for any task to complete
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            completed_line_results = [task.result() for task in done]
            # persist node run infos and flow run info in line result to storage
            self._persist_run_info(completed_line_results)
            line_results.extend(completed_line_results)
            # update the progress log
            completed_line += len(completed_line_results)
            last_log_count = log_progress(
                run_start_time=self._start_time,
                total_count=total_lines,
                current_count=completed_line,
                last_log_count=last_log_count,
            )

    async def _exec_line_under_semaphore(
        self,
        semaphore,
        inputs: Mapping[str, Any],
        index: Optional[int] = None,
        run_id: Optional[str] = None,
    ):
        async with semaphore:
            return await self._executor_proxy.exec_line_async(inputs, index, run_id)

    def _should_exec_aggregation(self) -> bool:
        if self._is_eager_flow:
            return self._executor_proxy.has_aggregation
        aggregation_nodes = {node.name for node in self._flow.nodes if node.aggregation}
        return bool(aggregation_nodes)

    def _get_aggregation_inputs(self, batch_inputs, line_results: List[LineResult]):
        run_infos = [r.run_info for r in line_results]
        succeeded = [i for i, r in enumerate(run_infos) if r.status == Status.Completed]

        if self._is_eager_flow:
            return None, [
                AttrDict(output) if isinstance((output := line_results[i].output), dict) else output for i in succeeded
            ]

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
        return succeeded_inputs, succeeded_aggregation_inputs

    async def _exec_aggregation(
        self,
        batch_inputs: List[dict],
        line_results: List[LineResult],
        run_id: Optional[str] = None,
    ) -> AggregationResult:
        if not self._should_exec_aggregation():
            return AggregationResult({}, {}, {})

        name = "function" if self._is_eager_flow else "node"
        bulk_logger.info(f"Executing aggregation {name}...")

        try:
            inputs, aggregation_inputs = self._get_aggregation_inputs(batch_inputs, line_results)
            aggr_result = await self._executor_proxy.exec_aggregation_async(inputs, aggregation_inputs, run_id)
            # if the flow language is python, we have already persisted node run infos during execution.
            # so we should persist node run infos in aggr_result for other languages.
            if not isinstance(self._executor_proxy, PythonExecutorProxy):
                for node_run in aggr_result.node_run_infos.values():
                    self._storage.persist_node_run(node_run)
            bulk_logger.info(f"Finish executing aggregation {name}.")
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

    def _batch_timeout_expired(self) -> bool:
        # Currently, local PythonExecutorProxy will handle the batch timeout by itself.
        if self._batch_timeout_sec is None or (
            not self._batch_use_async and isinstance(self._executor_proxy, PythonExecutorProxy)
        ):
            return False
        return (datetime.utcnow() - self._start_time).total_seconds() > self._batch_timeout_sec
