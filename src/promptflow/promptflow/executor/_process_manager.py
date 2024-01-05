import multiprocessing
import queue
import signal
from functools import partial
import psutil
from promptflow._core.operation_context import OperationContext
from promptflow._utils.logger_utils import LogContext, bulk_logger
from promptflow.executor.flow_executor import FlowExecutor


class ProcessManager:
    def __init__(
        self,
        input_queues,
        output_queues,
        process_info,
        process_target_func,
        raise_ex,
    ) -> None:
        self._input_queues = input_queues
        self._output_queues = output_queues
        self._process_info = process_info
        self._process_target_func = process_target_func
        self._raise_ex = raise_ex
        self._current_log_context = LogContext.get_current()
        self._log_context_initialization_func = (
            self._current_log_context.get_initializer() if self._current_log_context else None)
        self._current_operation_context = OperationContext.get_instance().get_context_dict()

    def new_process(self, idx):
        pass

    def restart_process(self, idx):
        pass

    def end_process(self, idx):
        pass


class SpawnProcessManager(ProcessManager):
    def __init__(
            self,
            executor_creation_func,
            *args,
            **kwargs):
        super().__init__(*args, **kwargs)
        self._executor_creation_func = executor_creation_func
        self.context = multiprocessing.get_context("spawn")

    def start_processes(self):
        for i in range(len(self._input_queues)):
            self.new_process(i)

    def new_process(self, i):
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
        self._process_info[i] = {'pid': process.pid, 'process_name': process.name}
        return process

    def restart_process(self, i):
        self.end_process(i)
        self.new_process(i)

    def end_process(self, i):
        try:
            pid = self._process_info[i]['pid']
            process = psutil.Process(pid)
            process.terminate()
            process.wait()
            self._process_info.pop(i)
        except psutil.NoSuchProcess:
            bulk_logger.warning(f"Process {pid} had been terminated")


class ForkProcessManager(ProcessManager):
    def __init__(
            self,
            control_signal_queue,
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

    def restart_processes(self, idx):
        self._control_signal_queue.put(('restart', idx))

    def end_process(self, idx):
        self._control_signal_queue.put(('end', idx))

    def new_process(self, idx):
        self._control_signal_queue.put(('start', idx))


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
    from promptflow.executor._line_execution_process_pool import signal_handler, create_executor_fork
    signal.signal(signal.SIGINT, signal_handler)
    context = multiprocessing.get_context("fork")
    executor = FlowExecutor.create(
        flow_file=flow_file,
        connections=connections,
        working_dir=working_dir,
        raise_ex=raise_ex,
    )

    executor_creation_func = partial(create_executor_fork, flow_executor=executor)

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
        process_info[i] = {'pid': process.pid, 'process_name': process.name}
        return process

    for i in range(len(input_queues)):
        new_process(i)

    def end_process(i):
        try:
            pid = process_info[i]['pid']
            process = psutil.Process(pid)
            process.terminate()
            process.wait()
            process_info.pop(i)
        except psutil.NoSuchProcess:
            bulk_logger.warning(f"Process {pid} had been terminated")

    def handle_signals(control_signal, i):
        if control_signal == "end":
            end_process(i)
        elif control_signal == "restart":
            end_process(i)
            new_process(i)
        elif control_signal == 'start':
            new_process(i)

    while True:
        all_processes_stopped = True
        for _, info in list(process_info.items()):
            pid = info['pid']
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
