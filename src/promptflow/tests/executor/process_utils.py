import contextlib
import multiprocessing
import traceback
from multiprocessing import Queue, get_context

from promptflow.executor._line_execution_process_pool import _process_wrapper
from promptflow.executor._process_manager import create_spawned_fork_process_manager


def _run_in_subprocess(error_queue: Queue, func, args, kwargs):
    try:
        func(*args, **kwargs)
    except BaseException as e:
        error_queue.put((repr(e), traceback.format_exc()))


def execute_function_in_subprocess(func, *args, **kwargs):
    """
    Execute a function in a new process and return any exception that occurs.
    Replace pickle with dill for better serialization capabilities.
    """
    ctx = get_context("spawn")
    error_queue = ctx.Queue()
    process = ctx.Process(target=_run_in_subprocess, args=(error_queue, func, args, kwargs))
    process.start()
    process.join()  # Wait for the process to finish

    if not error_queue.empty():
        err, stacktrace_str = error_queue.get()
        raise Exception(f"An error occurred in the subprocess: {err}\nStacktrace:\n{stacktrace_str}")
    assert process.exitcode == 0, f"Subprocess exited with code {process.exitcode}"


SpawnProcess = multiprocessing.Process
if "spawn" in multiprocessing.get_all_start_methods():
    SpawnProcess = multiprocessing.get_context("spawn").Process


ForkServerProcess = multiprocessing.Process
if "forkserver" in multiprocessing.get_all_start_methods():
    ForkServerProcess = multiprocessing.get_context("forkserver").Process


class BaseMockProcess:
    # Base class for the mock process; This class is mainly used as the placeholder for the target mocking logic
    def modify_target(self, target):
        # Method to modify the target of the mock process
        # This shall be the place to hold the target mocking logic
        if target == _process_wrapper:
            return current_process_wrapper
        if target == create_spawned_fork_process_manager:
            return current_process_manager
        return target


class MockSpawnProcess(SpawnProcess, BaseMockProcess):
    def __init__(self, group=None, target=None, *args, **kwargs):
        modified_target = self.modify_target(target)
        super().__init__(group, modified_target, *args, **kwargs)


class MockForkServerProcess(ForkServerProcess, BaseMockProcess):
    def __init__(self, group=None, target=None, *args, **kwargs):
        modified_target = self.modify_target(target)
        super().__init__(group, modified_target, *args, **kwargs)


current_process_wrapper = None
current_process_manager = None


@contextlib.contextmanager
def enable_mock_in_process(process_wrapper=None, process_manager=None):
    global current_process_wrapper, current_process_manager
    original_process_wrapper = current_process_wrapper
    original_process_manager = current_process_manager
    # Set to the customized ones if provided
    if process_wrapper is not None:
        current_process_wrapper = process_wrapper
    if process_manager is not None:
        current_process_manager = process_manager

    try:
        yield
    finally:
        # Revert back to the original states
        current_process_wrapper = original_process_wrapper
        current_process_manager = original_process_manager
