import contextlib
import contextvars
import multiprocessing
import traceback
from multiprocessing import Queue, get_context

from promptflow.executor._line_execution_process_pool import _process_wrapper
from promptflow.executor._process_manager import create_spawned_fork_process_manager

from .record_utils import setup_recording


def _run_in_subprocess(error_queue: Queue, func, args, kwargs):
    try:
        func(*args, **kwargs)
    except BaseException as e:
        error_queue.put((repr(e), traceback.format_exc()))


def _run_in_subprocess_with_recording(*args, **kwargs):
    process_class_dict = {"spawn": MockSpawnProcess, "forkserver": MockForkServerProcess}
    override_process_class(process_class_dict)

    # recording injection again since this method is running in a new process
    setup_recording()
    _run_in_subprocess(*args, **kwargs)


def execute_function_in_subprocess(func, *args, **kwargs):
    """
    Execute a function in a new process and return any exception that occurs.
    Replace pickle with dill for better serialization capabilities.
    """
    ctx = get_context("spawn")
    error_queue = ctx.Queue()
    process = ctx.Process(target=_run_in_subprocess_with_recording, args=(error_queue, func, args, kwargs))
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


# Define context variables with default values
current_process_wrapper_var = contextvars.ContextVar("current_process_wrapper", default=_process_wrapper)
current_process_manager_var = contextvars.ContextVar(
    "current_process_manager", default=create_spawned_fork_process_manager
)


class BaseMockProcess:
    # Base class for the mock process; This class is mainly used as the placeholder for the target mocking logic
    def modify_target(self, target):
        # Method to modify the target of the mock process
        # This shall be the place to hold the target mocking logic
        if target == _process_wrapper:
            return current_process_wrapper_var.get()
        if target == create_spawned_fork_process_manager:
            return current_process_manager_var.get()
        return target


class MockSpawnProcess(SpawnProcess, BaseMockProcess):
    def __init__(self, group=None, target=None, *args, **kwargs):
        modified_target = self.modify_target(target)
        super().__init__(group, modified_target, *args, **kwargs)


class MockForkServerProcess(ForkServerProcess, BaseMockProcess):
    def __init__(self, group=None, target=None, *args, **kwargs):
        modified_target = self.modify_target(target)
        super().__init__(group, modified_target, *args, **kwargs)


def override_process_class(process_class_dict: dict):
    original_process_class = {}
    for start_method, MockProcessClass in process_class_dict.items():
        if start_method in multiprocessing.get_all_start_methods():
            original_process_class[start_method] = multiprocessing.get_context(start_method).Process
            multiprocessing.get_context(start_method).Process = MockProcessClass
            if start_method == multiprocessing.get_start_method():
                multiprocessing.Process = MockProcessClass
    return original_process_class


@contextlib.contextmanager
def override_process_pool_targets(process_wrapper=None, process_manager=None):
    """
    Context manager to override the process pool targets for the current context

    """
    original_process_wrapper = current_process_wrapper_var.get()
    original_process_manager = current_process_manager_var.get()

    if process_wrapper is not None:
        current_process_wrapper_var.set(process_wrapper)
    if process_manager is not None:
        current_process_manager_var.set(process_manager)
    original_process_class = override_process_class({"spawn": MockSpawnProcess, "forkserver": MockForkServerProcess})

    try:
        yield
    finally:
        # Revert back to the original states
        current_process_wrapper_var.set(original_process_wrapper)
        current_process_manager_var.set(original_process_manager)
        override_process_class(original_process_class)
