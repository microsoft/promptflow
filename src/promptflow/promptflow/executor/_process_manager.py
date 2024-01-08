import multiprocessing
from multiprocessing import Queue
from typing import List
import queue
import signal
from functools import partial
from dataclasses import dataclass
import psutil
from promptflow._core.operation_context import OperationContext
from promptflow._utils.logger_utils import LogContext, bulk_logger
from promptflow.executor.flow_executor import FlowExecutor


@dataclass
class ProcessInfo:
    process_id: str = None
    process_name: str = None


class AbstractProcessManager:
    '''
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
    '''

    def __init__(
        self,
        input_queues: List[Queue],
        output_queues: List[Queue],
        process_info: dict,
        process_target_func,
        raise_ex: bool,
    ) -> None:
        self._input_queues = input_queues
        self._output_queues = output_queues
        self._process_info = process_info
        self._process_target_func = process_target_func
        self._raise_ex = raise_ex

        current_log_context = LogContext.get_current()
        self._log_context_initialization_func = (
            current_log_context.get_initializer() if current_log_context else None)
        self._current_operation_context = OperationContext.get_instance().get_context_dict()

    def new_process(self, i):
        # i: Index of the new process to start.
        pass

    def restart_process(self, i):
        # i: Index of the process to restart.
        pass

    def end_process(self, i):
        # i: Index of the process to end.
        pass


class SpawnProcessManager(AbstractProcessManager):
    '''
    SpawnProcessManager extends AbstractProcessManager to specifically manage processes using the 'spawn' start method.

    :param executor_creation_func: Function to create an executor for each process.

    :param args: Additional positional arguments for the AbstractProcessManager.
    :param kwargs: Additional keyword arguments for the AbstractProcessManager.
    '''

    def __init__(
            self,
            executor_creation_func,
            *args,
            **kwargs):
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
                self._current_operation_context
            ),
            # Set the process as a daemon process to automatically terminated and release system resources
            # when the main process exits.
            daemon=True,
        )

        process.start()
        self._process_info[i] = ProcessInfo(process_id=process.pid, process_name=process.name)
        return process

    def restart_process(self, i):
        """
        Restarts a specified process by first terminating it then creating a new one.

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
            process = psutil.Process(pid)
            process.terminate()
            process.wait()
            self._process_info.pop(i)
        except psutil.NoSuchProcess:
            bulk_logger.warning(f"Process {pid} had been terminated")


class ForkProcessManager(AbstractProcessManager):
    '''
    ForkProcessManager extends AbstractProcessManager to manage processes using the 'fork' method.

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

    def __init__(
            self,
            control_signal_queue: Queue,
            flow_file,
            connections,
            working_dir,
            *args,
            **kwargs):
        super().__init__(*args, **kwargs)
        self._control_signal_queue = control_signal_queue
        self._flow_file = flow_file
        self._connections = connections
        self._working_dir = working_dir

    def start_processes(self):
        '''
        Initiates a process using the 'spawn' method.
        '''
        context = multiprocessing.get_context("spawn")
        process = context.Process(
            target=fork_processes_manager,
            args=(
                self._log_context_initialization_func,
                self._current_operation_context,
                self._input_queues,
                self._output_queues,
                self._control_signal_queue,
                self._flow_file,
                self._connections,
                self._working_dir,
                self._raise_ex,
                self._process_info,
                self._process_target_func
            )
        )
        process.start()

    def restart_processes(self, i):
        """
        Sends a signal to restart a specific process.

        :param i: Index of the process to restart.
        :type i: int
        """
        self._control_signal_queue.put(('restart', i))

    def end_process(self, i):
        """
        Sends a signal to terminate a specific process.

        :param i: Index of the process to terminate.
        :type i: int
        """
        self._control_signal_queue.put(('end', i))

    def new_process(self, i):
        """
        Sends a signal to start a new process.

        :param i: Index of the new process to start.
        :type i: int
        """
        self._control_signal_queue.put(('start', i))


def fork_processes_manager(
        log_context_initialization_func,
        current_operation_context,
        input_queues,
        output_queues,
        control_signal_queue,
        flow_file,
        connections,
        working_dir,
        raise_ex,
        process_info,
        process_target_func
):
    """
    Manages the creation, termination, and signaling of processes using the 'fork' context.
    """
    # Set up signal handling for process interruption.
    from promptflow.executor._line_execution_process_pool import signal_handler, create_executor_fork
    signal.signal(signal.SIGINT, signal_handler)

    # Set the multiprocessing context to 'fork'.
    context = multiprocessing.get_context("fork")

    # Create flow executor.
    executor = FlowExecutor.create(
        flow_file=flow_file,
        connections=connections,
        working_dir=working_dir,
        raise_ex=raise_ex,
    )

    executor_creation_func = partial(create_executor_fork, flow_executor=executor)

    # Function to create and start a new process.
    def new_process(i):
        process = context.Process(
            target=process_target_func,
            args=(
                executor_creation_func,
                input_queues[i],
                output_queues[i],
                log_context_initialization_func,
                current_operation_context
            ),
            daemon=True
        )
        process.start()
        process_info[i] = ProcessInfo(process_id=process.pid, process_name=process.name)
        return process

    # Initialize processes.
    for i in range(len(input_queues)):
        new_process(i)

    # Function to terminate a process.
    def end_process(i):
        try:
            pid = process_info[i].process_id
            process = psutil.Process(pid)
            process.terminate()
            process.wait()
            process_info.pop(i)
        except psutil.NoSuchProcess:
            bulk_logger.warning(f"Process {pid} had been terminated")

    # Function to handle control signals for processes.
    def handle_signals(control_signal, i):
        if control_signal == "end":
            end_process(i)
        elif control_signal == "restart":
            end_process(i)
            new_process(i)
        elif control_signal == 'start':
            new_process(i)

    # Main loop to handle control signals and manage process lifecycle.
    while True:
        all_processes_stopped = True
        for _, info in list(process_info.items()):
            pid = info.process_id
            # Check if at least one process is alive.
            if psutil.pid_exists(pid):
                process = psutil.Process(pid)
                if process.status() != 'zombie':
                    all_processes_stopped = False
                else:
                    # If do not call wait(), the child process may become a zombie process,
                    # and psutil.pid_exists(pid) is always true, which will cause spawn proces
                    # never exit.
                    process.wait()

        # If all fork child processes exit, exit the loop.
        if all_processes_stopped:
            break
        try:
            control_signal, i = control_signal_queue.get(timeout=1)
            handle_signals(control_signal, i)
        except queue.Empty:
            # Do nothing until the process_queue have not content or process is killed
            pass
