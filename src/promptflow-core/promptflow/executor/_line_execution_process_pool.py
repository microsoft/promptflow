# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import asyncio
import contextvars
import multiprocessing
import os
import queue
import shutil
import signal
import sys
import threading
import uuid
from contextlib import nullcontext
from datetime import datetime
from functools import partial
from logging import INFO
from multiprocessing import Manager, Queue
from multiprocessing.pool import ThreadPool
from pathlib import Path
from tempfile import mkdtemp
from typing import Callable, Dict, List, Optional, Union

import psutil

from promptflow._constants import LINE_NUMBER_KEY, LINE_TIMEOUT_SEC
from promptflow._core._errors import ProcessPoolError, UnexpectedError
from promptflow._core.run_tracker import RunTracker
from promptflow._utils.dataclass_serializer import convert_dataclass_to_dict
from promptflow._utils.exception_utils import ExceptionPresenter
from promptflow._utils.logger_utils import bulk_logger
from promptflow._utils.process_utils import (
    get_available_max_worker_count,
    get_manager_process_log_path,
    get_subprocess_log_path,
    log_errors_from_file,
)
from promptflow._utils.thread_utils import RepeatLogTimer
from promptflow._utils.utils import log_progress, set_context
from promptflow.contracts.run_info import FlowRunInfo
from promptflow.contracts.run_info import RunInfo as NodeRunInfo
from promptflow.contracts.run_info import Status
from promptflow.exceptions import ErrorTarget, PromptflowException
from promptflow.executor._errors import (
    BatchExecutionTimeoutError,
    LineExecutionTimeoutError,
    ProcessCrashError,
    ThreadCrashError,
)
from promptflow.executor._process_manager import (
    ForkProcessManager,
    ProcessControlSignal,
    ProcessInfo,
    ProcessPoolConstants,
    SpawnProcessManager,
)
from promptflow.executor._result import LineResult
from promptflow.executor._script_executor import ScriptExecutor
from promptflow.executor.flow_executor import DEFAULT_CONCURRENCY_BULK, FlowExecutor
from promptflow.storage._queue_run_storage import QueueRunStorage
from promptflow.storage._service_storage import ServiceStorage
from promptflow.tracing._operation_context import OperationContext


class LineExecutionProcessPool:
    """A process pool for executing lines in batch mode.

    :param output_dir: The output directory for the batch run.
    :param flow_executor: The flow executor used to provide flow_create_kwargs to execute the lines.
    :param worker_count: The number of worker processes in the pool.
    :param line_timeout_sec: The timeout for each line execution in seconds.
    :param batch_timeout_sec: The timeout for the entire batch run in seconds.
    :param run_id: The run id of the batch run.
    :param nlines: The number of lines in the batch run.
    :param persist_multimedia_after_execution: Persist multimedia after execution or during execution.
        If True, will persist multimedia data after get LineResult from the output queue.
        If False, will persist multimedia data during the line execution.
    """

    _DEFAULT_WORKER_COUNT = 4
    _THREAD_TERMINATED_TIMEOUT = 10
    _PROCESS_TERMINATED_TIMEOUT = 60
    _PROCESS_INFO_OBTAINED_TIMEOUT = 60

    def __init__(
        self,
        output_dir: Path,
        flow_executor: FlowExecutor,
        worker_count: Optional[int] = None,
        line_timeout_sec: Optional[int] = None,
        batch_timeout_sec: Optional[int] = None,
        run_id: Optional[str] = None,
        nlines: Optional[int] = None,
        persist_multimedia_after_execution: bool = False,
    ):
        # Determine whether to use fork to create process.
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

        # Initialize some fields from the init parameters.
        self._nlines = nlines
        self._run_id = run_id
        self._output_dir = output_dir
        self._batch_timeout_sec = batch_timeout_sec
        self._line_timeout_sec = line_timeout_sec or LINE_TIMEOUT_SEC
        self._worker_count = self._determine_worker_count(worker_count)
        self._persist_multimedia_after_execution = persist_multimedia_after_execution

        # Initialize the results dictionary that stores line results.
        self._result_dict: Dict[str, LineResult] = {}

        # Initialize some fields from flow_executor and construct flow_create_kwargs
        self._flow_id = flow_executor._flow_id
        self._log_interval = flow_executor._log_interval
        self._flow_create_kwargs = {
            "flow_file": flow_executor._flow_file,
            "connections": flow_executor._connections,
            "working_dir": flow_executor._working_dir,
            "line_timeout_sec": self._line_timeout_sec,
            "raise_ex": False,
            # only script executor has init
            "init_kwargs": getattr(flow_executor, "_init_kwargs", None),
        }
        if isinstance(flow_executor, ScriptExecutor):
            self._storage = flow_executor._storage
        else:
            self._storage = flow_executor._run_tracker._storage
            # ScriptExecutor does not have _flow attribute.
            self._flow_create_kwargs.update({"name": flow_executor._flow.name})
        # Will set to True if the batch run is timeouted.
        self._is_timeout = False
        self._multimedia_processor = flow_executor._multimedia_processor

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @property
    def is_timeout(self):
        return self._is_timeout

    def start(self):
        """Start the process pool and create a thread pool monitoring process status"""
        manager = Manager()
        self._processing_idx = manager.dict()
        self._completed_idx = manager.dict()

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
        self._monitor_pool = ThreadPool(
            self._n_process, initializer=set_context, initargs=(contextvars.copy_context(),)
        )
        # The variable '_async_tasks' here is a list of AsyncResult object
        # that can be used to check if the execution are finished.
        # The actual line results of the batch run are stored in 'result_dict'.

        # Create _n_process monitoring threads, mainly used to assign tasks and receive line result.
        # When receiving terminate signal, end the process.
        # When line execution timeout or process crash, restart the process.
        self._async_tasks = [
            self._monitor_pool.apply_async(
                func=self._monitor_workers_and_process_tasks_in_thread,
                args=(
                    self._task_queue,  # Shared task queue for all sub processes to read the input data.
                    self._result_dict,  # Line result dict of the batch run.
                    i,  # Index of the sub process.
                    self._input_queues[i],  # Specific input queue for sub process, used to send input data to it.
                    self._output_queues[i],  # Specific output queue for sub process, used to receive results from it.
                ),
            )
            for i in range(self._n_process)
        ]

    def close(self):
        """End the process pool and close the thread pool."""
        # Terminate the task of monitor threads.
        self._terminate_tasks()
        # Close the thread pool and wait for all threads to complete.
        if self._monitor_pool is not None:
            self._monitor_pool.close()
            self._monitor_pool.join()
        # If a thread crashed for some reason, the processes it monitors might not be able to exit because
        # they do not receive a terminate signal. So we need to terminate these unmonitored processes.
        self._processes_manager.ensure_all_processes_terminated()
        # In fork mode, send the 'spawned_manager_end' signal to exit the spawned process manager.
        if self._use_fork:
            self._control_signal_queue.put((ProcessControlSignal.SPAWNED_MANAGER_END, self._use_fork))
        # Clear the result dict.
        self._result_dict.clear()
        # Delete log files to prevent interference from the current run on the next execution.
        self._delete_log_files()

    async def submit(self, run_id: str, line_number: int, inputs: dict):
        """Submit a line execution request to the process pool and return the line result."""
        request_id = get_request_id()
        self._task_queue.put((request_id, run_id, line_number, inputs))
        start_time = datetime.utcnow()
        line_result = None
        while not self._line_timeout_expired(start_time, buffer_sec=20) and not line_result:
            line_result = self._result_dict.pop(request_id, None)
            # Check monitor status every 1 second
            self._monitor_thread_pool_status()
            await asyncio.sleep(1)
        return line_result

    async def run(self, batch_inputs) -> List[LineResult]:
        """Submit all batch inputs to the process pool and return the line results."""
        with RepeatLogTimer(
            interval_seconds=self._log_interval,
            logger=bulk_logger,
            level=INFO,
            log_message_function=self._generate_thread_status_messages,
            args=(
                self._monitor_pool,
                self._nlines,
            ),
        ):
            try:
                self._batch_start_time = datetime.utcnow()
                # After starting time, put the input in self._task_queue, because the monitor thread will
                # use self._batch_start_time to calculate the remain execution time after get the input data.
                for index, inputs in batch_inputs:
                    self._task_queue.put(
                        (
                            get_request_id(),
                            self._run_id,
                            index,
                            inputs,
                        )
                    )
                # Wait for batch run to complete or timeout
                last_log_count = 0
                while not self._batch_timeout_expired(self._batch_start_time):
                    # Print the progress logs of the batch run.
                    last_log_count = log_progress(
                        run_start_time=self._batch_start_time,
                        total_count=self._nlines,
                        current_count=len(self._result_dict),
                        last_log_count=last_log_count,
                    )
                    # If the batch run is completed, break the loop.
                    if self._is_batch_run_completed():
                        break
                    # Check monitor status every 1 second
                    self._monitor_thread_pool_status()
                    await asyncio.sleep(1)
            except PromptflowException:
                raise
            except Exception as e:
                bulk_logger.error(f"ProcessPool failed with exception: {e}")
                raise ProcessPoolError(
                    message_format=f"ProcessPool failed with exception: {e}",
                    target=ErrorTarget.EXECUTOR,
                ) from e

        if self._batch_timeout_expired(self._batch_start_time):
            # Send terminate signal to all threads and wait for them to exit.
            self._terminate_tasks()
            # Wait for up to 10s for thread termination, aiming to ensure that
            # the line results in the result dict are as complete as possible.
            start_time = datetime.utcnow()
            while not self._timeout_expired(start_time, self._THREAD_TERMINATED_TIMEOUT):
                if self._all_tasks_ready():
                    break
                await asyncio.sleep(1)
            # Set the timeout flag to True and log the warning.
            self._is_timeout = True
            bulk_logger.warning(f"The batch run timed out, with {len(self._result_dict)} line results processed.")
        return [line_result for line_result in sorted(self._result_dict.values(), key=lambda item: item.run_info.index)]

    # region monitor thread target function

    def _monitor_workers_and_process_tasks_in_thread(
        self,
        task_queue: Queue,
        result_dict: Dict[str, LineResult],
        index: int,
        input_queue: Queue,
        output_queue: Queue,
    ):
        # Get the process info of the thread monitoring from the manager.
        index, process_id, process_name = self._processes_manager.get_process_info(index)

        # The main loop of the thread, responsible for getting tasks from the task queue and
        # processing them through the input queue, while also monitoring for terminate signals.
        # Currently, it exits this loop only upon receiving a terminate signal or the batch run timeout.
        terminated = False
        while not terminated:
            self._processes_manager.ensure_healthy()
            # Get task from task_queue
            data = self._get_task_from_queue(task_queue)
            # Calculate the line timeout for the current line.
            # If the line_timeout_sec is None, it means the batch run is timeouted.
            line_timeout_sec = self._calculate_line_timeout_sec()
            # If the task is a terminate signal or the batch run is timeouted, exit the loop.
            if data == ProcessPoolConstants.TERMINATE_SIGNAL or line_timeout_sec is None:
                bulk_logger.info(f"The thread monitoring the process [{process_id}-{process_name}] will be terminated.")
                # Put the terminate signal into the input queue to notify the sub process to exit.
                input_queue.put(ProcessPoolConstants.TERMINATE_SIGNAL)
                # End the process if found the terminate signal.
                self._processes_manager.end_process(index)
                # In fork mode, the main process and the sub spawn process communicate through _process_info.
                # We need to ensure the process has been killed before returning. Otherwise, it may cause
                # the main process have exited but the spawn process is still alive.
                # At this time, a connection error will be reported.
                self._processes_manager.ensure_process_terminated_within_timeout(process_id)
                # Set terminated to True to exit the main loop.
                terminated = True
            else:
                # If the task is a line execution request, put the request into the input queue.
                request_id, run_id, line_number, inputs = data
                args = (run_id, line_number, inputs, line_timeout_sec)
                input_queue.put(args)

            if terminated:
                break

            start_time = datetime.utcnow()
            completed = False
            crashed = False
            returned_node_run_infos = {}

            self._processing_idx[line_number] = format_current_process_info(process_name, process_id, line_number)
            log_process_status(process_name, process_id, line_number)
            # Responsible for checking the output queue messages and processing them within a specified timeout period.
            while not self._line_timeout_expired(start_time, line_timeout_sec=line_timeout_sec):
                # Monitor process aliveness.
                crashed = not self._processes_manager.is_process_alive(process_id)
                if crashed:
                    break

                # Handle output queue message.
                message = self._handle_output_queue_messages(output_queue)
                if isinstance(message, LineResult):
                    result_dict[request_id] = message
                    completed = True
                    break
                if isinstance(message, NodeRunInfo):
                    returned_node_run_infos[message.node] = message

            # Handle line execution completed.
            if completed:
                self._completed_idx[line_number] = format_current_process_info(process_name, process_id, line_number)
                log_process_status(process_name, process_id, line_number, is_completed=True)
            # Handle line execution is not completed.
            else:
                ex = None
                # Handle process crashed.
                if crashed:
                    bulk_logger.warning(f"Process crashed while executing line {line_number}.")
                    log_path = get_subprocess_log_path(index)
                    # In fork mode, if the child process fails to start, its error information
                    # will be written to the parent process log file.
                    # So if 'log_errors_form_path' return 'false', it means the child process fails to start.
                    # Attempt read the parent process log file.
                    if not log_errors_from_file(log_path) and self._use_fork:
                        log_path = get_manager_process_log_path()
                        log_errors_from_file(log_path)
                    ex = ProcessCrashError(line_number)
                elif self._line_timeout_expired(start_time, line_timeout_sec=line_timeout_sec):
                    # Handle line execution timeout.
                    bulk_logger.warning(f"Line {line_number} timeout after {line_timeout_sec} seconds.")
                    if line_timeout_sec < self._line_timeout_sec:
                        # If execution times out with a timeout lower than the default (self._line_timeout_sec),
                        # it indicates the _batch_timeout_sec has been reached.
                        # We should use the exception of BatchExecutionTimeoutError.
                        ex = BatchExecutionTimeoutError(line_number, self._batch_timeout_sec)
                    else:
                        ex = LineExecutionTimeoutError(line_number, line_timeout_sec)
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
                result_dict[request_id] = result

                self._completed_idx[line_number] = format_current_process_info(process_name, process_id, line_number)
                log_process_status(process_name, process_id, line_number, is_failed=True)

                self._processes_manager.restart_process(index)
                # We need to ensure the process has been killed before continuing to execute.
                # Otherwise the process will receive new task, and during the execution, the process
                # is killed, which will result in the 'ProcessCrashError'.
                self._processes_manager.ensure_process_terminated_within_timeout(process_id)
                index, process_id, process_name = self._processes_manager.get_process_info(index)

            self._processing_idx.pop(line_number)

    # endregion

    # region private methods
    def _delete_log_files(self):
        try:
            shutil.rmtree(ProcessPoolConstants.PROCESS_LOG_PATH)
        except Exception:
            # Ignore the exception when deleting the log files.
            pass

    def _get_task_from_queue(self, task_queue: Queue):
        """Get task from the task queue. Ignore the queue being empty and only exit the loop when getting data."""
        while True:
            try:
                return task_queue.get(timeout=1)
            except queue.Empty:
                pass

    def _all_tasks_ready(self):
        return all(async_task.ready() for async_task in self._async_tasks)

    def _terminate_tasks(self):
        if self._all_tasks_ready():
            return
        # Put n (equal to processes number) terminate signals to the task queue to ensure each thread receives one.
        for _ in range(self._n_process):
            self._task_queue.put(ProcessPoolConstants.TERMINATE_SIGNAL)

    def _determine_worker_count(self, worker_count):
        # Starting a new process in non-fork mode requires to allocate memory.
        # Calculate the maximum number of processes based on available memory to avoid memory bursting.
        estimated_available_worker_count = get_available_max_worker_count() if not self._use_fork else None

        # If the environment variable PF_WORKER_COUNT exists and valid, use the value as the worker_count.
        if worker_count is not None and worker_count > 0:
            bulk_logger.info(f"Set process count to {worker_count}.")
            if estimated_available_worker_count is not None and estimated_available_worker_count < worker_count:
                bulk_logger.warning(
                    f"The current process count ({worker_count}) is larger than recommended process count "
                    f"({estimated_available_worker_count}) that estimated by system available memory. This may "
                    f"cause memory exhaustion"
                )
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

    def _calculate_line_timeout_sec(self):
        """Calculate the line timeout for the current line."""
        line_timeout_sec = self._line_timeout_sec
        if self._batch_timeout_sec:
            remaining_execution_time = int(
                round(self._batch_timeout_sec - (datetime.utcnow() - self._batch_start_time).total_seconds())
            )
            if remaining_execution_time <= 0:
                self._is_timeout = True
                return None
            line_timeout_sec = min(line_timeout_sec, remaining_execution_time)
        return line_timeout_sec

    def _monitor_thread_pool_status(self):
        try:
            for async_task in self._async_tasks:
                if not async_task.ready():
                    continue
                # To ensure exceptions in thread-pool calls are propagated to the main process for proper handling
                # The exceptions raised will be re-raised by the get() method.
                # Related link:
                # https://docs.python.org/3/library/multiprocessing.html#multiprocessing.pool.AsyncResult
                async_task.get()
        except PromptflowException:
            raise
        except Exception as e:
            raise ThreadCrashError(
                target=ErrorTarget.BATCH,
                message_format="The monitor thread in the process pool crashed. Error: {error_type_and_message}.",
                error_type_and_message=f"({e.__class__.__name__}) {e}",
            ) from e

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

    def _is_batch_run_completed(self):
        return len(self._result_dict) == self._nlines

    def _batch_timeout_expired(self, start_time: datetime) -> bool:
        if self._batch_timeout_sec is None:
            return False
        return self._timeout_expired(start_time, self._batch_timeout_sec + 10)

    def _line_timeout_expired(self, start_time: datetime, line_timeout_sec: int = None, buffer_sec: int = 10) -> bool:
        # Here we add more seconds (buffer_sec) because of the following reasons:
        # 1. At the last second, there would be several timeout message from exec_line.
        # 2. It may take time to create worker so actual timeout time may be longer.
        # 3. When using submit function to submit one line, the buffer_sec should be
        #    larger than the monitor thread's internal buffer time.
        line_timeout_sec = line_timeout_sec or self._line_timeout_sec
        return self._timeout_expired(start_time, line_timeout_sec + buffer_sec)

    def _timeout_expired(self, start_time: datetime, timeout_sec: int) -> bool:
        return (datetime.utcnow() - start_time).total_seconds() > timeout_sec

    def _handle_output_queue_messages(self, output_queue: Queue):
        try:
            message = output_queue.get(timeout=1)
            if isinstance(message, LineResult):
                message = self._process_multimedia(message)
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

    def _process_multimedia(self, result: LineResult) -> LineResult:
        if not self._output_dir:
            return result
        if self._persist_multimedia_after_execution:
            self._persist_multimedia_to_output_dir(result)
        else:
            self._persist_multimedia_to_string(result)
        # Persist multimedia data in the outputs of line result to output_dir
        result.output = self._multimedia_processor.persist_multimedia_data(result.output, self._output_dir)
        return result

    def _persist_multimedia_to_output_dir(self, result: LineResult):
        """Persist multimedia data in the line result to output_dir to ensure
        the multimedia data path is correct in the line result."""
        service_storage = ServiceStorage(self._output_dir)
        # Persist multimedia data in flow run info to output_dir
        service_storage.persist_flow_run(result.run_info)
        # Persist multimedia data in node run infos to output_dir
        for node_run_info in result.node_run_infos.values():
            service_storage.persist_node_run(node_run_info)
        # Persist multimedia data in the aggregation_inputs of line result to temp dir
        result.aggregation_inputs = self._multimedia_processor.persist_multimedia_data(
            result.aggregation_inputs, Path(mkdtemp()), use_absolute_path=True
        )

    def _persist_multimedia_to_string(self, result: LineResult):
        """Replace multimedia data in line result with string place holder to
        prevent OOM and persist multimedia data in output when batch running."""
        # Serialize multimedia data in flow run info to string
        self._convert_multimedia_to_string(result.run_info)
        # Serialize multimedia data in node run infos to string
        for node_run_info in result.node_run_infos.values():
            self._convert_multimedia_to_string(node_run_info)

    def _convert_multimedia_to_string(self, run_info: Union[FlowRunInfo, NodeRunInfo]):
        if run_info.inputs:
            run_info.inputs = self._multimedia_processor.convert_multimedia_data_to_string(run_info.inputs)

        if run_info.output:
            serialized_output = self._multimedia_processor.convert_multimedia_data_to_string(run_info.output)
            run_info.output = serialized_output
            run_info.result = None

        # The `inplace=True` parameter is used here to ensure that the original list structure holding generator outputs
        # is maintained. This allows us to keep tracking the list as it dynamically changes when the generator is
        # consumed. It is crucial to process the api_calls list in place to avoid losing the reference to the list that
        # holds the generator items, which is essential for tracing generator execution.
        if run_info.api_calls:
            run_info.api_calls = self._multimedia_processor.convert_multimedia_data_to_string(
                run_info.api_calls, inplace=True
            )

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

    # endregion


# region process target functions


def _process_wrapper(
    executor_creation_func,
    input_queue: Queue,
    output_queue: Queue,
    log_context_initialization_func,
    operation_contexts_dict: dict,
    i: int,
):
    ProcessPoolConstants.PROCESS_LOG_PATH.mkdir(parents=True, exist_ok=True)
    log_path = get_subprocess_log_path(i)
    sys.stderr = open(log_path, "w")

    if threading.current_thread() is threading.main_thread():
        signal.signal(signal.SIGINT, signal_handler)
    else:
        bulk_logger.info("Current thread is not main thread, skip signal handler registration in batch process pool.")
    OperationContext.get_instance().update(operation_contexts_dict)  # Update the operation context for the new process.

    _exec_line_for_queue(
        executor_creation_func,
        input_queue,
        output_queue,
        log_context_initialization_func,
    )


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


def _exec_line_for_queue(
    executor_creation_func,
    input_queue: Queue,
    output_queue: Queue,
    log_context_initialization_func: Optional[Callable] = None,
):
    executor: FlowExecutor = executor_creation_func(storage=QueueRunStorage(output_queue))

    while True:
        try:
            data = input_queue.get(timeout=1)
            if data == ProcessPoolConstants.TERMINATE_SIGNAL:
                # Set logger context for terminate signal without line_number.
                with log_context_initialization_func() if log_context_initialization_func else nullcontext():
                    bulk_logger.info(f"The process [{os.getpid()}] has received a terminate signal.")
                    # Add try catch in case of shutdown method is not implemented in the tracer provider.
                    try:
                        import opentelemetry.trace as otel_trace

                        # Meet span missing issue when end process normally (even add wait() when end it).
                        # Shutdown the tracer provider to flush the remaining spans.
                        # The tracer provider is created for each process, so it's ok to shutdown it here.
                        tracer_provider = otel_trace.get_tracer_provider()
                        if hasattr(tracer_provider, "shutdown"):
                            tracer_provider.shutdown()
                    except Exception as e:
                        bulk_logger.warning(f"Error occurred while shutting down tracer provider: {e}")

                    # If found the terminate signal, exit the process.
                    break
            run_id, line_number, inputs, line_timeout_sec = data
            # Set logger context for each line execution. Because we also need to record line logs in batch run.
            with log_context_initialization_func(
                line_number=line_number
            ) if log_context_initialization_func else nullcontext():
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
            if isinstance(line_result.output, dict):
                line_result.output.pop(LINE_NUMBER_KEY, None)
            # For eager flow, the output may be a dataclass which is not picklable, we need to convert it to dict.
            line_result.output = convert_dataclass_to_dict(line_result.output)
        # TODO: Put serialized line result into queue to catch serialization error beforehand.
        # Otherwise it might cause the process to hang, e.g, line failed because output is not seralizable.
        if line_result is not None and line_result.run_info.status == Status.Failed:
            line_result.output = {}
        return line_result
    except Exception as e:
        bulk_logger.error(f"Line {index}, Process {os.getpid()} failed with exception: {e}")
        flow_id = executor._flow_id
        line_run_id = run_id if index is None else f"{run_id}_{index}"
        message_format = executor._message_format
        # If line execution failed before start, there is no flow information in the run_tracker.
        # So we call start_flow_run before handling exception to make sure the run_tracker has flow info.
        if isinstance(executor, ScriptExecutor):
            run_tracker = RunTracker(executor._storage)
        else:
            run_tracker = executor._run_tracker
        run_tracker.start_flow_run(flow_id, run_id, line_run_id, run_id, index=index, message_format=message_format)
        run_info = run_tracker.end_run(f"{run_id}_{index}", ex=e)
        output_queue.put(run_info)
        result = LineResult(
            output={},
            aggregation_inputs={},
            run_info=run_info,
            node_run_infos={},
        )
        return result


# endregion


# region utils function


def log_process_status(process_name, pid, line_number: int, is_completed=False, is_failed=False):
    process_info = format_current_process_info(process_name, pid, line_number)
    if is_completed:
        bulk_logger.info(f"{process_info} completed.")
    elif is_failed:
        bulk_logger.info(f"{process_info} failed.")
    else:
        bulk_logger.info(f"{process_info} start execution.")


def format_current_process_info(process_name, pid, line_number: int):
    return f"Process name({process_name})-Process id({pid})-Line number({line_number})"


def get_request_id() -> str:
    """
    Treat each input as a request to the line process pool and
    get the id of each request to use it as the key for the result_dict.
    """
    return str(uuid.uuid4())


# endregion
