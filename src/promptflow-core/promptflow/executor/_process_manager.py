import multiprocessing
import queue
import signal
import sys
import time
from dataclasses import dataclass
from enum import Enum
from functools import partial
from multiprocessing import Process, Queue
from pathlib import Path
from typing import Dict, List

import psutil

from promptflow._core.run_tracker import RunTracker
from promptflow._utils.logger_utils import LogContext, bulk_logger
from promptflow._utils.process_utils import get_manager_process_log_path, get_subprocess_log_path, log_errors_from_file
from promptflow.executor._errors import (
    ProcessInfoObtainedTimeout,
    ProcessTerminatedTimeout,
    SpawnedForkProcessManagerStartFailure,
)
from promptflow.executor._prompty_executor import PromptyExecutor
from promptflow.executor._script_executor import ScriptExecutor
from promptflow.executor.flow_executor import FlowExecutor
from promptflow.storage import AbstractRunStorage
from promptflow.tracing._operation_context import OperationContext


@dataclass
class ProcessInfo:
    index: int
    process_id: str
    process_name: str


class ProcessPoolConstants:
    PROCESS_LOG_PATH = Path("process_log")
    PROCESS_LOG_NAME = "process_stderr"
    MANAGER_PROCESS_LOG_NAME = "manager_process_stderr.log"
    TERMINATE_SIGNAL = "terminate"


class ProcessControlSignal(str, Enum):
    START = "start"
    RESTART = "restart"
    END = "end"
    SPAWNED_MANAGER_END = "spawned_manager_end"


class AbstractProcessManager:
    """
    AbstractProcessManager is a base class for managing processes.

    :param input_queues: Queues for providing input data to the processes.
    :type input_queues: List[multiprocessing.Queue]

    :param output_queues: Queues for receiving execution results of the processes.
    :type output_queues: List[multiprocessing.Queue]

    :param process_info: Dictionary to store information about the processes.
    :type process_info: dict

    :param process_target_func: The target function that the processes will execute.

    :param raise_ex: Flag to determine whether to raise exceptions or not.
    :type raise_ex: bool
    """

    _PROCESS_TERMINATED_TIMEOUT = 60
    _PROCESS_INFO_OBTAINED_TIMEOUT = 60

    def __init__(
        self,
        input_queues: List[Queue],
        output_queues: List[Queue],
        process_info: dict,
        process_target_func,
        *args,
        **kwargs,
    ) -> None:
        self._input_queues = input_queues
        self._output_queues = output_queues
        self._process_info: Dict[int, ProcessInfo] = process_info
        self._process_target_func = process_target_func
        current_log_context = LogContext.get_current()
        self._log_context_initialization_func = current_log_context.get_initializer() if current_log_context else None
        self._current_operation_context = OperationContext.get_instance().get_context_dict()

    def new_process(self, i):
        """
        Create and start a new process.

        :param i: Index of the new process to start.
        :type i: int
        """
        raise NotImplementedError("AbstractProcessManager is an abstract class, no implementation for new_process.")

    def restart_process(self, i):
        """
        Restarts a specified process

        :param i: Index of the process to restart.
        :type i: int
        """
        self.end_process(i)
        self.new_process(i)

    def end_process(self, i):
        """
        Terminates a specified process.

        :param i: Index of the process to terminate.
        :type i: int
        """
        try:
            pid = self._process_info[i].process_id
            self._terminate_process(i, pid)
        finally:
            self._process_info.pop(i)

    def ensure_healthy(self):
        """
        Checks the health of the managed processes.

        This method should be implemented in subclasses to provide specific health check mechanisms.
        """
        raise NotImplementedError("AbstractProcessManager is an abstract class, no implementation for end_process.")

    def get_process_info(self, index):
        start_time = time.time()
        while True:
            self.ensure_healthy()
            try:
                if time.time() - start_time > self._PROCESS_INFO_OBTAINED_TIMEOUT:
                    log_path = get_subprocess_log_path(index)
                    if not log_errors_from_file(log_path):
                        log_path = get_manager_process_log_path()
                        log_errors_from_file(log_path)
                    raise ProcessInfoObtainedTimeout(self._PROCESS_INFO_OBTAINED_TIMEOUT)
                # Try to get process id and name from the process_info
                process_id = self._process_info[index].process_id
                process_name = self._process_info[index].process_name
                return (index, process_id, process_name)
            except KeyError:
                # If the process_info does not exist for the given index, it means the process have not ready yet,
                # try again.
                time.sleep(1)
                continue
            except Exception as e:
                raise Exception(f"Unexpected error occurred while get process info. Exception: {e}")

    def ensure_process_terminated_within_timeout(self, process_id):
        start_time = time.time()
        while psutil.pid_exists(process_id):
            if time.time() - start_time > self._PROCESS_TERMINATED_TIMEOUT:
                raise ProcessTerminatedTimeout(self._PROCESS_TERMINATED_TIMEOUT)
            time.sleep(1)

    def ensure_all_processes_terminated(self):
        for i, info in self._process_info.items():
            self._terminate_process(i, info.process_id)

    def is_process_alive(self, process_id):
        return psutil.pid_exists(process_id)

    def _terminate_process(self, i, pid):
        warning_msg = "Unexpected error occurred while end process for index {i} and process id {pid}. Exception: {e}"
        try:
            process = psutil.Process(pid)
            # The subprocess will get terminate signal from input queue, so we need to wait for the process to exit.
            # If the process is still running after 10 seconds, it will raise psutil.TimeoutExpired exception.
            process.wait(timeout=10)
            bulk_logger.info(f"Process {pid} terminated.")
        except psutil.NoSuchProcess:
            bulk_logger.warning(f"Process {pid} had been terminated.")
        except psutil.TimeoutExpired:
            try:
                # If the process is still running after waiting 10 seconds, terminate it.
                process.terminate()
                process.wait()
                bulk_logger.info(f"Process {pid} terminated.")
            except Exception as e:
                bulk_logger.warning(warning_msg.format(i=i, pid=pid, e=e))
        except Exception as e:
            bulk_logger.warning(warning_msg.format(i=i, pid=pid, e=e))


class SpawnProcessManager(AbstractProcessManager):
    """
    SpawnProcessManager extends AbstractProcessManager to specifically manage processes using the 'spawn' start method.

    :param executor_creation_func: Function to create an executor for each process.

    :param args: Additional positional arguments for the AbstractProcessManager.
    :param kwargs: Additional keyword arguments for the AbstractProcessManager.
    """

    def __init__(self, executor_creation_func, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._executor_creation_func = executor_creation_func
        self.context = multiprocessing.get_context("spawn")

    def start_processes(self):
        """
        Initiates processes.
        """
        for i in range(len(self._input_queues)):
            self.new_process(i)

    def new_process(self, i):
        """
        Create and start a new process using the 'spawn' context.

        :param i: Index of the input and output queue for the new process.
        :type i: int
        """
        process = self.context.Process(
            target=self._process_target_func,
            args=(
                self._executor_creation_func,
                self._input_queues[i],
                self._output_queues[i],
                self._log_context_initialization_func,
                self._current_operation_context,
                i,
            ),
            # Set the process as a daemon process to automatically terminated and release system resources
            # when the main process exits.
            daemon=True,
        )

        process.start()
        try:
            self._process_info[i] = ProcessInfo(
                index=i,
                process_id=process.pid,
                process_name=process.name,
            )
        except Exception as e:
            bulk_logger.warning(
                f"Unexpected error occurred while creating ProcessInfo for index {i} and process id {process.pid}. "
                f"Exception: {e}"
            )
        return process

    def ensure_healthy(self):
        """
        Checks the health of the managed processes.

        Note:
        Health checks for spawn mode processes are currently not performed.
        Add detailed checks in this function if needed in the future.
        """
        pass


class ForkProcessManager(AbstractProcessManager):
    '''
    ForkProcessManager extends AbstractProcessManager to manage processes using the 'fork' method
    in a spawned process.

    :param control_signal_queue: A queue for controlling signals to manage process operations.
    :type control_signal_queue: multiprocessing.Queue

    :param flow_file: The path to the flow file.
    :type flow_file: Path

    :param connections: The connections to be used for the flow.
    :type connections: dict

    :param working_dir: The working directory to be used for the flow.
    :type working_dir: str

    :param args: Additional positional arguments for the AbstractProcessManager.
    :param kwargs: Additional keyword arguments for the AbstractProcessManager.
    """
    '''

    def __init__(self, control_signal_queue: Queue, flow_create_kwargs, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._control_signal_queue = control_signal_queue
        self._flow_create_kwargs = flow_create_kwargs
        # Use _kwargs to temporarily store all common kwargs and pass them to SpawnedForkProcessManager
        self._kwargs = kwargs

    def start_processes(self):
        """
        Initiates a process with "spawn" method to establish a clean environment.
        """
        context = multiprocessing.get_context("spawn")
        process = context.Process(
            target=create_spawned_fork_process_manager,
            args=(
                self._log_context_initialization_func,
                self._current_operation_context,
                self._control_signal_queue,
                self._flow_create_kwargs,
            ),
            kwargs=self._kwargs,
        )
        process.start()
        self._spawned_fork_process_manager_pid = process.pid

    def restart_process(self, i):
        """
        Sends a signal to restart a specific process.

        :param i: Index of the process to restart.
        :type i: int
        """
        self._control_signal_queue.put((ProcessControlSignal.RESTART, i))

    def end_process(self, i):
        """
        Sends a signal to terminate a specific process.

        :param i: Index of the process to terminate.
        :type i: int
        """
        self._control_signal_queue.put((ProcessControlSignal.END, i))

    def new_process(self, i):
        """
        Sends a signal to start a new process.

        :param i: Index of the new process to start.
        :type i: int
        """
        self._control_signal_queue.put((ProcessControlSignal.START, i))

    def ensure_healthy(self):
        # A 'zombie' process is a process that has finished running but still remains in
        # the process table, waiting for its parent process to collect and handle its exit status.
        # The normal state of the spawned process is 'running'. If the process does not start successfully
        # or exit unexpectedly, its state will be 'zombie'.
        if psutil.Process(self._spawned_fork_process_manager_pid).status() == "zombie":
            log_path = get_manager_process_log_path()
            try:
                with open(log_path, "r") as f:
                    error_logs = "".join(f.readlines())
                    bulk_logger.error(error_logs)
            except FileNotFoundError:
                pass
            bulk_logger.error("The spawned fork process manager failed to start.")
            ex = SpawnedForkProcessManagerStartFailure()
            raise ex


class SpawnedForkProcessManager(AbstractProcessManager):
    """
    SpawnedForkProcessManager extends AbstractProcessManager to manage processes using 'fork' method
    in a spawned process.

    :param control_signal_queue: A queue for controlling signals to manage process operations.
    :type control_signal_queue: multiprocessing.Queue

    :param executor_creation_func: Function to create an executor for each process.
    :type executor_creation_func: Callable

    :param args: Additional positional arguments for the AbstractProcessManager.
    :param kwargs: Additional keyword arguments for the AbstractProcessManager.
    """

    def __init__(
        self,
        log_context_initialization_func,
        current_operation_context,
        control_signal_queue,
        executor_creation_func,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self._log_context_initialization_func = log_context_initialization_func
        self._current_operation_context = current_operation_context
        self._control_signal_queue = control_signal_queue
        self._executor_creation_func = executor_creation_func
        self.context = multiprocessing.get_context("fork")

    def new_process(self, i):
        """
        Create and start a new process using the 'fork' context.

        :param i: Index of the input and output queue for the new process.
        :type i: int
        """
        process: Process = self.context.Process(
            target=self._process_target_func,
            args=(
                self._executor_creation_func,
                self._input_queues[i],
                self._output_queues[i],
                self._log_context_initialization_func,
                self._current_operation_context,
                i,
            ),
            daemon=True,
        )
        process.start()
        try:
            self._process_info[i] = ProcessInfo(
                index=i,
                process_id=process.pid,
                process_name=process.name,
            )
        except Exception as e:
            bulk_logger.warning(
                f"Unexpected error occurred while creating ProcessInfo for index {i} and process id {process.pid}. "
                f"Exception: {e}"
            )
        return process

    def handle_signals(self, control_signal, i):
        """
        Handles control signals for processes, performing actions such as starting, ending,
        or restarting them based on the received signal.

        :param control_signal: The control signal indicating the desired action. It can be 'start', 'end', or 'restart'.
        :type control_signal: str

        :param i: Index of the process to control.
        :type i: int
        """
        if control_signal == ProcessControlSignal.END:
            self.end_process(i)
        elif control_signal == ProcessControlSignal.RESTART:
            self.restart_process(i)
        elif control_signal == ProcessControlSignal.START:
            self.new_process(i)


def create_spawned_fork_process_manager(
    log_context_initialization_func,
    current_operation_context,
    control_signal_queue,
    flow_create_kwargs,
    **kwargs,
):
    ProcessPoolConstants.PROCESS_LOG_PATH.mkdir(parents=True, exist_ok=True)
    log_path = get_manager_process_log_path()
    sys.stderr = open(log_path, "w")

    """
    Manages the creation, termination, and signaling of processes using the 'fork' context.
    """
    # Set up signal handling for process interruption.

    from promptflow.executor._line_execution_process_pool import signal_handler

    signal.signal(signal.SIGINT, signal_handler)

    # Create flow executor.
    executor = FlowExecutor.create(**flow_create_kwargs)

    # When using fork, we use this method to create the executor to avoid reloading the flow
    # which will introduce a lot more memory.
    executor_creation_func = partial(_create_executor_fork, flow_executor=executor)

    manager = SpawnedForkProcessManager(
        log_context_initialization_func,
        current_operation_context,
        control_signal_queue,
        executor_creation_func,
        **kwargs,
    )

    # Initialize processes.
    for i in range(len(manager._input_queues)):
        manager.new_process(i)

    # Main loop to handle control signals and manage process lifecycle.
    while True:
        try:
            process_info_list = manager._process_info.items()
        except Exception as e:
            bulk_logger.warning(f"Unexpected error occurred while get process info list. Exception: {e}")
            break

        for _, info in list(process_info_list):
            pid = info.process_id
            # Check if at least one process is alive.
            if psutil.pid_exists(pid):
                process = psutil.Process(pid)
                if process.status() == "zombie":
                    # If do not call wait(), the child process may become a zombie process,
                    # and psutil.pid_exists(pid) is always true, which will cause spawn proces
                    # never exit.
                    process.wait()

        try:
            control_signal, i = control_signal_queue.get(timeout=1)
            # Exit the spawned process manager.
            if control_signal == ProcessControlSignal.SPAWNED_MANAGER_END and i is True:
                break
            else:
                manager.handle_signals(control_signal, i)
        except queue.Empty:
            # Do nothing until the process_queue have not content or process is killed
            pass


def _create_executor_fork(*, flow_executor: FlowExecutor, storage: AbstractRunStorage):
    if isinstance(flow_executor, PromptyExecutor):
        return PromptyExecutor(
            flow_file=flow_executor._flow_file,
            connections=flow_executor._connections,
            working_dir=flow_executor._working_dir,
            storage=storage,
            init_kwargs=flow_executor._init_kwargs,
        )
    if isinstance(flow_executor, ScriptExecutor):
        return ScriptExecutor(
            flow_file=flow_executor._flow_file,
            connections=flow_executor._connections,
            working_dir=flow_executor._working_dir,
            storage=storage,
            init_kwargs=flow_executor._init_kwargs,
        )
    else:
        run_tracker = RunTracker(run_storage=storage)
        return FlowExecutor(
            flow=flow_executor._flow,
            connections=flow_executor._connections,
            run_tracker=run_tracker,
            cache_manager=flow_executor._cache_manager,
            loaded_tools=flow_executor._loaded_tools,
            raise_ex=False,
            line_timeout_sec=flow_executor._line_timeout_sec,
        )
