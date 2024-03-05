import asyncio
import contextvars
import multiprocessing
import os
import queue
import signal
import sys
import threading
from datetime import datetime
from functools import partial
from multiprocessing import Manager, Queue
from multiprocessing.pool import ThreadPool
from pathlib import Path
from typing import Dict, Optional, Union

import psutil

from promptflow._constants import LINE_NUMBER_KEY, LINE_TIMEOUT_SEC
from promptflow._core._errors import UnexpectedError
from promptflow._core.operation_context import OperationContext
from promptflow._core.run_tracker import RunTracker
from promptflow._utils.dataclass_serializer import convert_eager_flow_output_to_dict
from promptflow._utils.exception_utils import ExceptionPresenter
from promptflow._utils.logger_utils import bulk_logger, service_logger
from promptflow._utils.multimedia_utils import _process_recursively, persist_multimedia_data
from promptflow._utils.utils import set_context
from promptflow.contracts.multimedia import Image
from promptflow.contracts.run_info import FlowRunInfo
from promptflow.contracts.run_info import RunInfo as NodeRunInfo
from promptflow.contracts.run_info import Status
from promptflow.executor._errors import LineExecutionTimeoutError, ProcessCrashError
from promptflow.executor._process_manager import ForkProcessManager, ProcessInfo, SpawnProcessManager
from promptflow.executor._result import LineResult
from promptflow.executor._script_executor import ScriptExecutor
from promptflow.executor.flow_executor import DEFAULT_CONCURRENCY_BULK, FlowExecutor
from promptflow.storage import AbstractRunStorage

TERMINATE_SIGNAL = "terminate"


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


def log_process_status(process_name, pid, line_number: int, is_completed=False, is_failed=False):
    process_info = f"Process name({process_name})-Process id({pid})-Line number({line_number})"
    if is_completed:
        bulk_logger.info(f"{process_info} completed.")
    elif is_failed:
        bulk_logger.info(f"{process_info} failed.")
    else:
        bulk_logger.info(f"{process_info} start execution.")


class LineExecutionProcessPool:
    _DEFAULT_WORKER_COUNT = 4
    _PROCESS_TERMINATED_TIMEOUT = 60
    _PROCESS_INFO_OBTAINED_TIMEOUT = 60

    def __init__(
        self,
        output_dir: Path,
        flow_executor: FlowExecutor,
        worker_count: Optional[int] = None,
        line_timeout_sec: Optional[int] = None,
    ):
        # Determine whether to use fork to create process
        multiprocessing_start_method = os.environ.get("PF_BATCH_METHOD", multiprocessing.get_start_method())
        sys_start_methods = multiprocessing.get_all_start_methods()
        if multiprocessing_start_method not in sys_start_methods:
            bulk_logger.warning(
                f"Failed to set start method to '{multiprocessing_start_method}', "
                f"start method {multiprocessing_start_method} is not in: {sys_start_methods}."
            )
            bulk_logger.info(f"Set start method to default {multiprocessing.get_start_method()}.")
            multiprocessing_start_method = multiprocessing.get_start_method()
        self._use_fork = multiprocessing_start_method in ["fork", "forkserver"]

        # Init some fields from inputs
        self._output_dir = output_dir
        self._result_dict: Dict[int, LineResult] = {}
        self._line_timeout_sec = line_timeout_sec or LINE_TIMEOUT_SEC
        self._worker_count = self._determine_worker_count(worker_count)

        # Init some fields from flow_executor
        self._flow_id = flow_executor._flow_id
        self._flow_file = flow_executor._flow_file
        self._connections = flow_executor._connections
        self._working_dir = flow_executor._working_dir
        if isinstance(flow_executor, ScriptExecutor):
            self._storage = flow_executor._storage
        else:
            self._storage = flow_executor._run_tracker._storage
        self._flow_create_kwargs = {
            "flow_file": flow_executor._flow_file,
            "connections": flow_executor._connections,
            "working_dir": flow_executor._working_dir,
            "line_timeout_sec": self._line_timeout_sec,
            "raise_ex": False,
        }

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end()

    def start(self):
        """Start the process pool and create a thread pool monitoring process status"""
        manager = Manager()

        self._task_queue = Queue()
        self._n_process = self._worker_count

        # When using fork, we first spawn a sub process, the SemLock created in fork context (multiprocessing.Queue()）
        # can't used in a spawn context. Since spawn does not share memory, synchronization primitives created by
        # fork cannot be used directly. It will cause an error: "A SemLock created in a fork context is being
        # shared with a process in a spawn context. This is not supported".

        # So use multiprocessing.Manager().Queue() instead of multiprocessing.Queue().
        # Manager().Queue() operates through a manager server process, which passes messages between different
        # processes without directly sharing memory state, which makes it safe to use in a spawn context.
        self._input_queues = [manager.Queue() for _ in range(self._n_process)]
        self._output_queues = [manager.Queue() for _ in range(self._n_process)]
        self._control_signal_queue = manager.Queue()
        process_info: Dict[int, ProcessInfo] = manager.dict()

        # when using fork, we first create a process with spawn method to establish a clean environment
        # Then fork the subprocess in this environment to avoid some deadlock problems
        common_kwargs = {
            "input_queues": self._input_queues,
            "output_queues": self._output_queues,
            "process_info": process_info,
            "process_target_func": _process_wrapper,
        }
        if self._use_fork:
            # 1. Create input_queue, output_queue, control_signal_queue and _process_info in the main process.
            # 2. Pass the above queue/dict as parameters to spawn and fork processes to transfer information
            # between processes.
            self._processes_manager = ForkProcessManager(
                self._control_signal_queue,
                self._flow_create_kwargs,
                **common_kwargs,
            )
        else:
            executor_creation_func = partial(FlowExecutor.create, **self._flow_create_kwargs)
            # 1. Create input_queue, output_queue, and _process_info in the main process.
            # 2. Spawn _n_process sub-process and pass the above queue/dict to these sub-process to transfer information
            # between main process and sub process.
            self._processes_manager = SpawnProcessManager(executor_creation_func, **common_kwargs)

        self._processes_manager.start_processes()
        self._processes_manager.ensure_healthy()

        # Start a thread pool to monitor the processes.
        monitor_pool = ThreadPool(self._n_process, initializer=set_context, initargs=(contextvars.copy_context(),))
        self._monitor_pool = monitor_pool
        args_list = [
            (
                self._task_queue,  # Shared task queue for all sub processes to read the input data.
                self._result_dict,  # Line result dict of the batch run.
                i,  # Index of the sub process.
                self._input_queues[i],  # Specific input queue for sub process, used to send input data to it.
                self._output_queues[i],  # Specific output queue for the sub process, used to receive results from it.
            )
            for i in range(self._n_process)
        ]
        self._monitor_pool.starmap_async(self._monitor_workers_and_process_tasks_in_thread, args_list)

    def end(self):
        """End the process pool and close the thread pool."""
        # Put n (equal to processes number) terminate signals to the task queue to ensure each thread receives one.
        for _ in range(self._n_process):
            self._task_queue.put(TERMINATE_SIGNAL)
        # Close the thread pool and wait for all threads to complete.
        if self._monitor_pool is not None:
            self._monitor_pool.close()
            self._monitor_pool.join()

    async def submit(self, inputs: dict, run_id: str, line_number: int):
        """Submit a line execution request to the process pool and return the line result."""
        self._task_queue.put((inputs, line_number, run_id))
        start_time = datetime.utcnow()
        line_result = None
        # TODO: time???????? +20?????
        while not self._line_timeout_expired(start_time) and not line_result:
            service_logger.info(f"line_result: {line_result}")
            line_result = self._result_dict.get(line_number, None)
            await asyncio.sleep(1)
        return line_result

    def _handle_output_queue_messages(self, output_queue: Queue, result_dict: Dict[int, LineResult], line_number: int):
        try:
            message = output_queue.get(timeout=1)
            if isinstance(message, LineResult):
                message = self._process_multimedia(message)
                result_dict[line_number] = message
                return message
            elif isinstance(message, FlowRunInfo):
                self._storage.persist_flow_run(message)
                return message
            elif isinstance(message, NodeRunInfo):
                self._storage.persist_node_run(message)
                return message
        except queue.Empty:
            pass
        return None

    def _monitor_workers_and_process_tasks_in_thread(
        self,
        task_queue: Queue,
        result_dict: Dict[int, LineResult],
        index: int,
        input_queue: Queue,
        output_queue: Queue,
    ):
        # Get the process info of the thread monitoring from the manager.
        index, process_id, process_name = self._processes_manager.get_process_info(index)
        self._processes_manager.ensure_healthy()

        # The main loop of the thread, responsible for getting tasks from the task queue and
        # processing them through the input queue, while also monitoring for terminate signals.
        # Currently, it exits this loop only upon receiving a terminate signal (TERMINATE_SIGNAL).
        exit_loop = False
        while not exit_loop:
            while True:
                try:
                    # Get task from task_queue
                    data = task_queue.get(timeout=1)
                    if data == TERMINATE_SIGNAL:
                        bulk_logger.info(
                            "The thread monitoring the process "
                            f"[{process_id}-{process_name}] has received a terminate signal."
                        )
                        # Put the terminate signal into the input queue to notify the sub process to exit.
                        input_queue.put(data)
                        # End the process if found the terminate signal.
                        self._processes_manager.end_process(index)
                        # In fork mode, the main process and the sub spawn process communicate through _process_info.
                        # We need to ensure the process has been killed before returning. Otherwise, it may cause
                        # the main process have exited but the spawn process is still alive.
                        # At this time, a connection error will be reported.
                        self._processes_manager.ensure_process_terminated_within_timeout(process_id)
                        # Set exit_loop to True to exit the main loop.
                        exit_loop = True
                        break
                    # TODO: Calculate the line timeout for the current line.???????
                    inputs, line_number, run_id = data
                    args = (inputs, line_number, run_id, self._line_timeout_sec)
                    input_queue.put(args)
                    break
                except queue.Empty:
                    pass

            if exit_loop:
                break

            start_time = datetime.utcnow()
            completed = False
            crashed = False
            returned_node_run_infos = {}

            log_process_status(process_name, process_id, line_number)
            # Responsible for checking the output queue messages and processing them within a specified timeout period.
            while not self._line_timeout_expired(start_time):
                # Monitor process aliveness.
                crashed = not self._processes_manager.is_process_alive(process_id)
                if crashed:
                    break

                # Handle output queue message.
                message = self._handle_output_queue_messages(output_queue, result_dict, line_number)
                if isinstance(message, LineResult):
                    completed = True
                    break
                if isinstance(message, NodeRunInfo):
                    returned_node_run_infos[message.node] = message

            # Handle line execution completed.
            if completed:
                log_process_status(process_name, process_id, line_number, is_completed=True)
            # Handle line execution is not completed.
            else:
                ex = None
                # Handle process crashed.
                if crashed:
                    bulk_logger.warning(f"Process crashed while executing line {line_number}.")
                    ex = ProcessCrashError(line_number)
                elif self._line_timeout_expired(start_time):
                    # Handle line execution timeout.
                    bulk_logger.warning(f"Line {line_number} timeout after {self._line_timeout_sec} seconds.")
                    ex = LineExecutionTimeoutError(line_number, self._line_timeout_sec)
                else:
                    # This branch should not be reached, add this warning for the case.
                    msg = f"Unexpected error occurred while monitoring line execution at line {line_number}."
                    bulk_logger.warning(msg)
                    ex = UnexpectedError(msg)

                result = self._generate_line_result_for_exception(
                    inputs,
                    run_id,
                    line_number,
                    self._flow_id,
                    start_time,
                    ex,
                    returned_node_run_infos,
                )
                result_dict[line_number] = result
                log_process_status(process_name, process_id, line_number, is_failed=True)

                self._processes_manager.restart_process(index)
                # We need to ensure the process has been killed before continuing to execute.
                # Otherwise the process will receive new task, and during the execution, the process
                # is killed, which will result in the 'ProcessCrashError'.
                self._processes_manager.ensure_process_terminated_within_timeout(process_id)
                index, process_id, process_name = self._processes_manager.get_process_info(index)

    def _line_timeout_expired(self, start_time: datetime) -> bool:
        # Here we add more seconds because of the following reasons:
        # 1. At the last second, there would be several timeout message from exec_line.
        # 2. It may take time to create worker so actual timeout time may be longer.
        return (datetime.utcnow() - start_time).total_seconds() > self._line_timeout_sec + 10

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

    def _generate_line_result_for_exception(
        self,
        inputs,
        run_id,
        line_number,
        flow_id,
        start_time,
        ex,
        node_run_infos={},
    ) -> LineResult:
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
            node_run_infos=node_run_infos,
        )
        # TODO: There is a corner case that the run info is persisted in the subprocess when timeouted,
        # while we also persist the run info here. This may cause duplicate run info in the storage.
        # We need to find a way to avoid this.
        self._storage.persist_flow_run(result.run_info)
        return result

    def _determine_worker_count(self, worker_count):
        # Starting a new process in non-fork mode requires to allocate memory.
        # Calculate the maximum number of processes based on available memory to avoid memory bursting.
        estimated_available_worker_count = get_available_max_worker_count() if not self._use_fork else None

        # If the environment variable PF_WORKER_COUNT exists and valid, use the value as the worker_count.
        if worker_count is not None and worker_count > 0:
            self._log_set_worker_count(worker_count, estimated_available_worker_count)
            return worker_count

        # If the environment variable PF_WORKER_COUNT is not set or invalid, take the minimum value among the
        # factors: default_worker_count, row_count and estimated_worker_count_based_on_memory_usage
        factors = {
            "default_worker_count": self._DEFAULT_WORKER_COUNT,
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
        bulk_logger.info(f"Set process count to {worker_count}.")
        if estimated_available_worker_count is not None and estimated_available_worker_count < worker_count:
            bulk_logger.warning(
                f"The current process count ({worker_count}) is larger than recommended process count "
                f"({estimated_available_worker_count}) that estimated by system available memory. This may "
                f"cause memory exhaustion"
            )


def _exec_line(
    executor: FlowExecutor, output_queue: Queue, *, inputs: dict, run_id: str, index: int, line_timeout_sec: int
):
    try:
        line_result = executor.exec_line(
            inputs=inputs,
            run_id=run_id,
            index=index,
            node_concurrency=DEFAULT_CONCURRENCY_BULK,
            line_timeout_sec=line_timeout_sec,
        )
        if line_result is not None:
            # For eager flow, the output may be a dataclass which is not picklable, we need to convert it to dict.
            if not isinstance(line_result.output, dict):
                line_result.output = convert_eager_flow_output_to_dict(line_result.output)
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
        if isinstance(executor, ScriptExecutor):
            run_tracker = RunTracker(executor._storage)
        else:
            run_tracker = executor._run_tracker
        run_tracker.start_flow_run(flow_id, run_id, line_run_id, run_id)
        run_info = run_tracker.end_run(f"{run_id}_{index}", ex=e)
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
    if threading.current_thread() is threading.main_thread():
        signal.signal(signal.SIGINT, signal_handler)
    else:
        bulk_logger.info("Current thread is not main thread, skip signal handler registration in batch process pool.")
    OperationContext.get_instance().update(operation_contexts_dict)  # Update the operation context for the new process.

    # set up OpenTelemetry exporter in process who executes the line
    from promptflow._trace._start_trace import setup_exporter_from_environ

    setup_exporter_from_environ()

    if log_context_initialization_func:
        with log_context_initialization_func():
            exec_line_for_queue(executor_creation_func, input_queue, output_queue)
    else:
        exec_line_for_queue(executor_creation_func, input_queue, output_queue)


def exec_line_for_queue(executor_creation_func, input_queue: Queue, output_queue: Queue):
    run_storage = QueueRunStorage(output_queue)
    executor: FlowExecutor = executor_creation_func(storage=run_storage)

    while True:
        try:
            data = input_queue.get(timeout=1)
            if data == TERMINATE_SIGNAL:
                service_logger.info("Process ... received terminate signal.")
                # If found the terminate signal, exit the process.
                break
            inputs, line_number, run_id, line_timeout_sec = data
            result = _exec_line(
                executor=executor,
                output_queue=output_queue,
                inputs=inputs,
                run_id=run_id,
                index=line_number,
                line_timeout_sec=line_timeout_sec,
            )
            output_queue.put(result)
        except queue.Empty:
            # Do nothing until the input_queue have content or process is killed
            # TODO: Exit the process more gracefully.
            pass


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
