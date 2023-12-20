import contextvars
import multiprocessing
import os
import queue
import signal
import sys
from datetime import datetime
from functools import partial
from logging import INFO
from multiprocessing import Manager, Queue
from multiprocessing.pool import ThreadPool
from typing import Union

import psutil

from promptflow._constants import LINE_NUMBER_KEY
from promptflow._core._errors import ProcessPoolError
from promptflow._core.operation_context import OperationContext
from promptflow._core.run_tracker import RunTracker
from promptflow._utils.exception_utils import ExceptionPresenter
from promptflow._utils.logger_utils import LogContext, bulk_logger
from promptflow._utils.multimedia_utils import _process_recursively, persist_multimedia_data
from promptflow._utils.thread_utils import RepeatLogTimer
from promptflow._utils.utils import get_int_env_var, log_progress, set_context
from promptflow.contracts.multimedia import Image
from promptflow.contracts.run_info import FlowRunInfo
from promptflow.contracts.run_info import RunInfo as NodeRunInfo
from promptflow.contracts.run_info import Status
from promptflow.exceptions import ErrorTarget, PromptflowException
from promptflow.executor._errors import LineExecutionTimeoutError
from promptflow.executor._result import LineResult
from promptflow.executor.flow_executor import DEFAULT_CONCURRENCY_BULK, FlowExecutor
from promptflow.storage import AbstractRunStorage


def signal_handler(signum, frame):
    signame = signal.Signals(signum).name
    bulk_logger.info("Execution stopping. Handling signal %s (%s)", signame, signum)
    try:
        process = psutil.Process(os.getpid())
        bulk_logger.info("Successfully terminated process with pid %s", process.pid)
        process.terminate()
    except Exception:
        bulk_logger.warning("Error when handling execution stop signal", exc_info=True)
    finally:
        sys.exit(1)


class QueueRunStorage(AbstractRunStorage):
    """This storage persists run info by putting it into a queue."""

    def __init__(self, queue: Queue):
        self.queue = queue

    def persist_node_run(self, run_info: NodeRunInfo):
        self.queue.put(run_info)

    def persist_flow_run(self, run_info: FlowRunInfo):
        self.queue.put(run_info)


class HealthyEnsuredProcess:
    def __init__(self, executor_creation_func, context):
        self.process = None
        self.input_queue = None
        self.output_queue = None
        self.is_ready = False
        self._executor_creation_func = executor_creation_func
        self.context = context

    def start_new(self, task_queue: Queue):
        input_queue = self.context.Queue()
        output_queue = self.context.Queue()
        self.input_queue = input_queue
        self.output_queue = output_queue

        # Put a start message and wait the subprocess be ready.
        # Test if the subprocess can receive the message.
        input_queue.put("start")

        current_log_context = LogContext.get_current()
        process = self.context.Process(
            target=_process_wrapper,
            args=(
                self._executor_creation_func,
                input_queue,
                output_queue,
                current_log_context.get_initializer() if current_log_context else None,
                OperationContext.get_instance().get_context_dict(),
            ),
            # Set the process as a daemon process to automatically terminated and release system resources
            # when the main process exits.
            daemon=True,
        )

        self.process = process
        process.start()

        try:
            # Wait for subprocess send a ready message.
            output_queue.get(timeout=30)
            self.is_ready = True
        except queue.Empty:
            self.end()
            # If there are no more tasks, the process is not re-created
            if not task_queue.empty():
                self.start_new(task_queue)

    def end(self):
        # When process failed to start and the task_queue is empty.
        # The process will no longer re-created, and the process is None.
        if self.process is None:
            return
        if self.process.is_alive():
            self.process.kill()

    def put(self, args):
        self.input_queue.put(args)

    def get(self):
        return self.output_queue.get(timeout=1)

    def format_current_process(self, line_number: int, is_completed=False):
        process_name = self.process.name if self.process else None
        process_pid = self.process.pid if self.process else None
        if is_completed:
            bulk_logger.info(
                f"Process name: {process_name}, Process id: {process_pid}, Line number: {line_number} completed."
            )
        else:
            bulk_logger.info(
                f"Process name: {process_name}, Process id: {process_pid}, Line number: {line_number} start execution."
            )

        return f"Process name({process_name})-Process id({process_pid})-Line number({line_number})"


class LineExecutionProcessPool:
    _DEFAULT_WORKER_COUNT = 16

    def __init__(
        self,
        flow_executor: FlowExecutor,
        nlines,
        run_id,
        variant_id,
        validate_inputs,
        output_dir,
    ):
        self._nlines = nlines
        self._run_id = run_id
        self._variant_id = variant_id
        self._validate_inputs = validate_inputs
        multiprocessing_start_method = os.environ.get("PF_BATCH_METHOD")
        sys_start_methods = multiprocessing.get_all_start_methods()
        if multiprocessing_start_method and multiprocessing_start_method not in sys_start_methods:
            bulk_logger.warning(
                f"Failed to set start method to '{multiprocessing_start_method}', "
                f"start method {multiprocessing_start_method} is not in: {sys_start_methods}."
            )
            bulk_logger.info(f"Set start method to default {multiprocessing.get_start_method()}.")
            multiprocessing_start_method = None
        self.context = get_multiprocessing_context(multiprocessing_start_method)
        use_fork = self.context.get_start_method() == "fork"
        # When using fork, we use this method to create the executor to avoid reloading the flow
        # which will introduce a lot more memory.
        if use_fork:
            self._executor_creation_func = partial(create_executor_fork, flow_executor=flow_executor)
        elif flow_executor._flow_file:
            self._executor_creation_func = partial(
                FlowExecutor.create,
                flow_file=flow_executor._flow_file,
                connections=flow_executor._connections,
                working_dir=flow_executor._working_dir,
                raise_ex=False,
            )
        else:  # Legacy flow executor, will be deprecated with the legacy pf portal.
            self._executor_creation_func = partial(
                create_executor_legacy,
                flow=flow_executor._flow,
                connections=flow_executor._connections,
                loaded_tools=flow_executor._loaded_tools,
                cache_manager=flow_executor._cache_manager,
            )
        self._use_fork = use_fork
        self._storage = flow_executor._run_tracker._storage
        self._flow_id = flow_executor._flow_id
        self._log_interval = flow_executor._log_interval
        self._line_timeout_sec = flow_executor._line_timeout_sec
        self._output_dir = output_dir

    def __enter__(self):
        manager = Manager()
        self._processing_idx = manager.dict()
        self._completed_idx = manager.dict()

        self._inputs_queue = Queue()
        self._n_process = self._determine_worker_count()

        pool = ThreadPool(self._n_process, initializer=set_context, initargs=(contextvars.copy_context(),))
        self._pool = pool

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._pool is not None:
            self._pool.close()
            self._pool.join()

    def _timeout_process_wrapper(self, run_start_time: datetime, task_queue: Queue, timeout_time, result_list):
        healthy_ensured_process = HealthyEnsuredProcess(self._executor_creation_func, self.context)
        healthy_ensured_process.start_new(task_queue)

        if not healthy_ensured_process.process.is_alive():
            return

        while True:
            try:
                args = task_queue.get(timeout=1)
            except queue.Empty:
                healthy_ensured_process.end()
                return

            healthy_ensured_process.put(args)
            inputs, line_number, run_id = args[:3]
            self._processing_idx[line_number] = healthy_ensured_process.format_current_process(line_number)

            start_time = datetime.utcnow()
            completed = False

            while datetime.utcnow().timestamp() - start_time.timestamp() <= timeout_time:
                try:
                    # Responsible for checking the output queue messages and
                    # processing them within a specified timeout period.
                    message = healthy_ensured_process.get()
                    if isinstance(message, LineResult):
                        completed = True
                        message = self._process_multimedia(message)
                        result_list.append(message)
                        break
                    elif isinstance(message, FlowRunInfo):
                        self._storage.persist_flow_run(message)
                    elif isinstance(message, NodeRunInfo):
                        self._storage.persist_node_run(message)
                except queue.Empty:
                    continue

            self._completed_idx[line_number] = healthy_ensured_process.format_current_process(line_number, True)
            # Handling the timeout of a line execution process.
            if not completed:
                bulk_logger.warning(f"Line {line_number} timeout after {timeout_time} seconds.")
                ex = LineExecutionTimeoutError(line_number, timeout_time)
                result = self._generate_line_result_for_exception(
                    inputs, run_id, line_number, self._flow_id, start_time, ex
                )
                result_list.append(result)
                self._completed_idx[line_number] = healthy_ensured_process.format_current_process(line_number, True)
                if not task_queue.empty():
                    healthy_ensured_process.end()
                    healthy_ensured_process.start_new(task_queue)

            self._processing_idx.pop(line_number)
            log_progress(
                run_start_time=run_start_time,
                logger=bulk_logger,
                count=len(result_list),
                total_count=self._nlines,
            )

    def _process_multimedia(self, result: LineResult) -> LineResult:
        """Replace multimedia data in line result with string place holder to prevent OOM
        and persist multimedia data in output when batch running."""
        if not self._output_dir:
            return result
        self._process_multimedia_in_flow_run(result.run_info)
        for node_name, node_run_info in result.node_run_infos.items():
            result.node_run_infos[node_name] = self._process_multimedia_in_node_run(node_run_info)
        result.output = persist_multimedia_data(result.output, self._output_dir)
        return result

    def _process_multimedia_in_run_info(self, run_info: Union[FlowRunInfo, NodeRunInfo]):
        # Persist and convert images in inputs to path dictionaries.
        # This replaces any image objects with their corresponding file path dictionaries.
        if run_info.inputs:
            run_info.inputs = self._persist_and_convert_images_to_path_dicts(run_info.inputs)

        # Persist and convert images in output to path dictionaries.
        # This replaces any image objects with their corresponding file path dictionaries.
        if run_info.output:
            serialized_output = self._persist_and_convert_images_to_path_dicts(run_info.output)
            run_info.output = serialized_output
            run_info.result = None

        # Persist and convert images in api_calls to path dictionaries.
        # The `inplace=True` parameter is used here to ensure that the original list structure holding generator outputs
        # is maintained. This allows us to keep tracking the list as it dynamically changes when the generator is
        # consumed. It is crucial to process the api_calls list in place to avoid losing the reference to the list that
        # holds the generator items, which is essential for tracing generator execution.
        if run_info.api_calls:
            run_info.api_calls = self._persist_and_convert_images_to_path_dicts(run_info.api_calls, inplace=True)

        return run_info

    def _process_multimedia_in_flow_run(self, run_info: FlowRunInfo):
        self._process_multimedia_in_run_info(run_info)

    def _process_multimedia_in_node_run(self, run_info: NodeRunInfo):
        run_info = self._process_multimedia_in_run_info(run_info)
        return run_info

    def _persist_and_convert_images_to_path_dicts(self, value, inplace=False):
        serialization_funcs = {Image: partial(Image.serialize, **{"encoder": None})}
        return _process_recursively(value, process_funcs=serialization_funcs, inplace=inplace)

    def _generate_line_result_for_exception(self, inputs, run_id, line_number, flow_id, start_time, ex) -> LineResult:
        bulk_logger.error(f"Line {line_number}, Process {os.getpid()} failed with exception: {ex}")
        run_info = FlowRunInfo(
            run_id=f"{run_id}_{line_number}",
            status=Status.Failed,
            error=ExceptionPresenter.create(ex).to_dict(include_debug_info=True),
            inputs=inputs,
            output=None,
            metrics=None,
            request=None,
            parent_run_id=run_id,
            root_run_id=run_id,
            source_run_id=None,
            flow_id=flow_id,
            start_time=start_time,
            end_time=datetime.utcnow(),
            index=line_number,
        )
        result = LineResult(
            output={},
            aggregation_inputs={},
            run_info=run_info,
            node_run_infos={},
        )
        self._storage.persist_flow_run(result.run_info)
        return result

    def run(self, batch_inputs):
        for index, inputs in batch_inputs:
            self._inputs_queue.put(
                (
                    inputs,
                    index,
                    self._run_id,
                    self._variant_id,
                    self._validate_inputs,
                )
            )

        result_list = []
        run_start_time = datetime.utcnow()

        with RepeatLogTimer(
            interval_seconds=self._log_interval,
            logger=bulk_logger,
            level=INFO,
            log_message_function=self._generate_thread_status_messages,
            args=(
                self._pool,
                self._nlines,
            ),
        ):
            try:
                # The variable 'async_result' here is not the actual result of the batch run
                # but an AsyncResult object that can be used to check if the execution are finished
                # The actual results of the batch run are stored in 'result_list'
                async_result = self._pool.starmap_async(
                    self._timeout_process_wrapper,
                    [
                        (run_start_time, self._inputs_queue, self._line_timeout_sec, result_list)
                        for _ in range(self._n_process)
                    ],
                )
                try:
                    # Wait for batch run to complete or KeyboardInterrupt
                    while not async_result.ready():
                        # Check every 1 second
                        async_result.wait(1)
                    # To ensure exceptions in thread-pool calls are propagated to the main process for proper handling
                    # The exceptions raised will be re-raised by the get() method.
                    # Related link:
                    # https://docs.python.org/3/library/multiprocessing.html#multiprocessing.pool.AsyncResult
                    async_result.get()
                except KeyboardInterrupt:
                    raise
            except PromptflowException:
                raise
            except Exception as e:
                bulk_logger.error(f"Process {os.getpid()} failed with exception: {e}")
                raise ProcessPoolError(
                    message_format=f"Process {os.getpid()} failed with exception: {e}",
                    target=ErrorTarget.EXECUTOR,
                ) from e
        return result_list

    def _generate_thread_status_messages(self, pool: ThreadPool, total_count: int):
        msgs = []
        active_threads = sum(thread.is_alive() for thread in pool._pool)
        msgs.append(f"[Process Pool] [Active processes: {active_threads} / {len(pool._pool)}]")
        processing_lines_copy = self._processing_idx.copy()
        completed_lines_copy = self._completed_idx.copy()
        msgs.append(
            f"[Lines] [Finished: {len(completed_lines_copy)}] [Processing: {len(processing_lines_copy)}] "
            f"[Pending: {total_count - len(processing_lines_copy) - len(completed_lines_copy)}]"
        )
        lines = []
        for idx, thread_name in sorted(processing_lines_copy.items()):
            lines.append(f"line {idx} ({thread_name})")
        if len(lines) > 0:
            msgs.append("Processing Lines: " + ", ".join(lines) + ".")
        return msgs

    def _determine_worker_count(self):
        worker_count = get_int_env_var("PF_WORKER_COUNT")

        # Starting a new process in non-fork mode requires to allocate memory. Calculate the maximum number of processes
        # based on available memory to avoid memory bursting.
        estimated_available_worker_count = get_available_max_worker_count() if not self._use_fork else None

        # If the environment variable PF_WORKER_COUNT exists and valid, use the value as the worker_count.
        if worker_count is not None and worker_count > 0:
            self._log_set_worker_count(worker_count, estimated_available_worker_count)
            return worker_count

        # If the environment variable PF_WORKER_COUNT is not set or invalid, take the minimum value among the
        # factors: default_worker_count, row_count and estimated_worker_count_based_on_memory_usage
        factors = {
            "default_worker_count": self._DEFAULT_WORKER_COUNT,
            "row_count": self._nlines,
            "estimated_worker_count_based_on_memory_usage": estimated_available_worker_count,
        }

        valid_factors = {k: v for k, v in factors.items() if v is not None and v > 0}

        # Take the minimum value as the result
        worker_count = min(valid_factors.values())
        bulk_logger.info(
            f"Set process count to {worker_count} by taking the minimum value among the factors of {valid_factors}."
        )
        return worker_count

    def _log_set_worker_count(self, worker_count, estimated_available_worker_count):
        bulk_logger.info(f"Set process count to {worker_count} with the environment variable 'PF_WORKER_COUNT'.")
        if estimated_available_worker_count is not None and estimated_available_worker_count < worker_count:
            bulk_logger.warning(
                f"The current process count ({worker_count}) is larger than recommended process count "
                f"({estimated_available_worker_count}) that estimated by system available memory. This may "
                f"cause memory exhaustion"
            )


def _exec_line(
    executor: FlowExecutor,
    output_queue,
    *,
    inputs: dict,
    run_id,
    index: int,
    variant_id,
    validate_inputs,
):
    try:
        line_result = executor.exec_line(
            inputs=inputs,
            run_id=run_id,
            index=index,
            variant_id=variant_id,
            validate_inputs=validate_inputs,
            node_concurrency=DEFAULT_CONCURRENCY_BULK,
        )
        if line_result is not None and isinstance(line_result.output, dict):
            line_result.output.pop(LINE_NUMBER_KEY, None)
        # TODO: Put serialized line result into queue to catch serialization error beforehand.
        # Otherwise it might cause the process to hang, e.g, line failed because output is not seralizable.
        if line_result is not None and line_result.run_info.status == Status.Failed:
            line_result.output = {}
        return line_result
    except Exception as e:
        bulk_logger.error(f"Line {index}, Process {os.getpid()} failed with exception: {e}")
        flow_id = executor._flow_id
        line_run_id = run_id if index is None else f"{run_id}_{index}"
        # If line execution failed before start, there is no flow information in the run_tracker.
        # So we call start_flow_run before handling exception to make sure the run_tracker has flow info.
        executor._run_tracker.start_flow_run(flow_id, run_id, line_run_id, run_id)
        run_info = executor._run_tracker.end_run(f"{run_id}_{index}", ex=e)
        output_queue.put(run_info)
        result = LineResult(
            output={},
            aggregation_inputs={},
            run_info=run_info,
            node_run_infos={},
        )
        return result


def _process_wrapper(
    executor_creation_func,
    input_queue: Queue,
    output_queue: Queue,
    log_context_initialization_func,
    operation_contexts_dict: dict,
):
    signal.signal(signal.SIGINT, signal_handler)
    OperationContext.get_instance().update(operation_contexts_dict)  # Update the operation context for the new process.
    if log_context_initialization_func:
        with log_context_initialization_func():
            bulk_logger.info(f"Process {os.getpid()} started.")
            exec_line_for_queue(executor_creation_func, input_queue, output_queue)
    else:
        exec_line_for_queue(executor_creation_func, input_queue, output_queue)


def create_executor_fork(*, flow_executor: FlowExecutor, storage: AbstractRunStorage):
    run_tracker = RunTracker(run_storage=storage, run_mode=flow_executor._run_tracker._run_mode)
    return FlowExecutor(
        flow=flow_executor._flow,
        connections=flow_executor._connections,
        run_tracker=run_tracker,
        cache_manager=flow_executor._cache_manager,
        loaded_tools=flow_executor._loaded_tools,
        raise_ex=False,
        line_timeout_sec=flow_executor._line_timeout_sec,
    )


def exec_line_for_queue(executor_creation_func, input_queue: Queue, output_queue: Queue):
    run_storage = QueueRunStorage(output_queue)
    executor: FlowExecutor = executor_creation_func(storage=run_storage)

    # Wait for the start signal message
    input_queue.get()

    # Send a ready signal message
    output_queue.put("ready")

    while True:
        try:
            args = input_queue.get(timeout=1)
            inputs, line_number, run_id, variant_id, validate_inputs = args[:5]
            result = _exec_line(
                executor=executor,
                output_queue=output_queue,
                inputs=inputs,
                run_id=run_id,
                index=line_number,
                variant_id=variant_id,
                validate_inputs=validate_inputs,
            )
            output_queue.put(result)
        except queue.Empty:
            # Do nothing until the input_queue have content or process is killed
            # TODO: Exit the process more gracefully.
            pass


def create_executor_legacy(*, flow, connections, loaded_tools, cache_manager, storage):
    """This is a legacy method to create a flow executor, will be deprecated with the legacy pf portal."""
    from promptflow._core.tool import ToolInvoker
    from promptflow.executor._tool_invoker import DefaultToolInvoker

    ToolInvoker.activate(DefaultToolInvoker())
    run_tracker = RunTracker(run_storage=storage)
    # import these to make sure LLM tool works.
    from promptflow.tools import aoai, openai  # noqa: F401

    return FlowExecutor(
        flow=flow,
        connections=connections,
        run_tracker=run_tracker,
        cache_manager=cache_manager,
        loaded_tools=loaded_tools,
        raise_ex=False,
    )


def get_available_max_worker_count():
    pid = os.getpid()
    mem_info = psutil.virtual_memory()
    available_memory = mem_info.available / (1024 * 1024)  # in MB
    process = psutil.Process(pid)
    process_memory_info = process.memory_info()
    process_memory = process_memory_info.rss / (1024 * 1024)  # in MB
    estimated_available_worker_count = int(available_memory // process_memory)
    if estimated_available_worker_count < 1:
        # TODO: For the case of vector db, Optimize execution logic
        # 1. Let the main process not consume memory because it does not actually invoke
        # 2. When the degree of parallelism is 1, main process executes the task directly and not
        #  create the child process
        bulk_logger.warning(
            f"Current system's available memory is {available_memory}MB, less than the memory "
            f"{process_memory}MB required by the process. The maximum available worker count is 1."
        )
        estimated_available_worker_count = 1
    else:
        bulk_logger.info(
            f"Current system's available memory is {available_memory}MB, "
            f"memory consumption of current process is {process_memory}MB, "
            f"estimated available worker count is {available_memory}/{process_memory} "
            f"= {estimated_available_worker_count}"
        )
    return estimated_available_worker_count


def get_multiprocessing_context(multiprocessing_start_method=None):
    if multiprocessing_start_method is not None:
        context = multiprocessing.get_context(multiprocessing_start_method)
        bulk_logger.info(f"Set start method to {multiprocessing_start_method}.")
        return context
    else:
        context = multiprocessing.get_context()
        return context
