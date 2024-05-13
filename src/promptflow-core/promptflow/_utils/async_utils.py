# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import asyncio
import functools
import signal
import threading
from typing import Iterator

from promptflow.tracing import ThreadPoolExecutorWithContext


def _has_running_loop() -> bool:
    """Check if the current thread has a running event loop."""
    # When using asyncio.get_running_loop(), a RuntimeError is raised if there is no running event loop.
    # So, we use a try-catch block to determine whether there is currently an event loop in place.
    #
    # Note that this is the only way to check whether there is a running loop now, see:
    # https://docs.python.org/3/library/asyncio-eventloop.html?highlight=get_running_loop#asyncio.get_running_loop
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False


class _AsyncTaskSigIntHandler:
    """The handler to cancel the current task if SIGINT is received.
    This is only for python<3.11 where the default cancelling behavior is not supported.
    The code is similar to the python>=3.11 builtin implementation.
    https://github.com/python/cpython/blob/46c808172fd3148e3397234b23674bf70734fb55/Lib/asyncio/runners.py#L150
    """

    def __init__(self, task: asyncio.Task, loop: asyncio.AbstractEventLoop):
        self._loop = loop
        self._task = task
        self._interrupt_count = 0

    def on_sigint(self, signum, frame):
        self._interrupt_count += 1
        if self._interrupt_count == 1 and not self._task.done():
            self._task.cancel()
            # This call_soon_threadsafe would schedule the call as soon as possible,
            # it would force the event loop to wake up then handle the cancellation request.
            # This is to avoid the loop blocking with long timeout.
            self._loop.call_soon_threadsafe(lambda: None)
            return
        raise KeyboardInterrupt()


async def _invoke_async_with_sigint_handler(async_func, *args, **kwargs):
    """In python>=3.11, when sigint is hit,
    asyncio.run in default cancel the running tasks before raising the KeyboardInterrupt,
    this introduces the chance to handle the cancelled error.
    So we have a similar implementation here so python<3.11 also have such feature.
    https://github.com/python/cpython/blob/46c808172fd3148e3397234b23674bf70734fb55/Lib/asyncio/runners.py#L150
    """
    # For the scenario that we don't need to update sigint, just return.
    # The scenarios include:
    # For python >= 3.11, asyncio.run already updated the sigint for cancelling tasks.
    # The user already has his own customized sigint.
    # The current code is not in main thread.
    if not _should_update_sigint():
        return await async_func(*args, **kwargs)
    try:
        loop = asyncio.get_running_loop()
        task = asyncio.create_task(async_func(*args, **kwargs))
        signal.signal(signal.SIGINT, _AsyncTaskSigIntHandler(task, loop).on_sigint)
        return await task
    finally:
        signal.signal(signal.SIGINT, signal.default_int_handler)


def _should_update_sigint():
    return (
        threading.current_thread() is threading.main_thread()
        and signal.getsignal(signal.SIGINT) is signal.default_int_handler
    )


def async_run_allowing_running_loop(async_func, *args, **kwargs):
    """Run an async function in a new thread, allowing the current thread to have a running event loop.

    When run in an async environment (e.g., in a notebook), because each thread allows only one event
    loop, using asyncio.run directly leads to a RuntimeError ("asyncio.run() cannot be called from a
    running event loop").

    To address this issue, we add a check for the event loop here. If the current thread already has an
    event loop, we run _exec_batch in a new thread; otherwise, we run it in the current thread.
    """
    if _has_running_loop():
        with ThreadPoolExecutorWithContext() as executor:
            return executor.submit(lambda: asyncio.run(async_func(*args, **kwargs))).result()
    else:
        return asyncio.run(_invoke_async_with_sigint_handler(async_func, *args, **kwargs))


def async_to_sync(func):
    def wrapper(*args, **kwargs):
        return async_run_allowing_running_loop(func, *args, **kwargs)

    return wrapper


def sync_to_async(func):
    async def wrapper(*args, **kwargs):
        with ThreadPoolExecutorWithContext() as executor:
            partial_func = functools.partial(func, *args, **kwargs)
            return await asyncio.get_event_loop().run_in_executor(executor, partial_func)

    return wrapper


async def sync_iterator_to_async(g: Iterator):
    with ThreadPoolExecutorWithContext(max_workers=1) as pool:
        loop = asyncio.get_running_loop()
        # Use object() as a default value to distinguish from None
        default_value = object()
        while True:
            resp = await loop.run_in_executor(pool, next, g, default_value)
            if resp is default_value:
                return
            yield resp
