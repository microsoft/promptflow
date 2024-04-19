import contextvars
from concurrent.futures import ThreadPoolExecutor
from typing import Callable


def set_context(context: contextvars.Context):
    for var, value in context.items():
        var.set(value)


def set_context_then_call(context: contextvars.Context, initializer: Callable, initargs=()):
    set_context(context)
    if initializer:
        initializer(*initargs)


class ThreadPoolExecutorWithContext(ThreadPoolExecutor):
    def __init__(self, max_workers=None, thread_name_prefix="", initializer=None, initargs=()):
        """The ThreadPoolExecutionWithContext is an extended thread pool implementation
        which will copy the context from the current thread to the child threads.
        Thus the traced functions in child threads could keep parent-child relationship in the tracing system.
        The arguments are the same as ThreadPoolExecutor.

        Args:
            max_workers: The maximum number of threads that can be used to
                execute the given calls.
            thread_name_prefix: An optional name prefix to give our threads.
            initializer: A callable used to initialize worker threads.
            initargs: A tuple of arguments to pass to the initializer.
        """
        current_context = contextvars.copy_context()
        initializer_args = (current_context, initializer, initargs)
        super().__init__(max_workers, thread_name_prefix, set_context_then_call, initializer_args)
