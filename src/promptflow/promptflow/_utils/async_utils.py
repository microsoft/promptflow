# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import asyncio
from concurrent.futures import ThreadPoolExecutor


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


def async_run_allowing_running_loop(async_func, *args, **kwargs):
    """Run an async function in a new thread, allowing the current thread to have a running event loop.

    When run in an async environment (e.g., in a notebook), because each thread allows only one event
    loop, using asyncio.run directly leads to a RuntimeError ("asyncio.run() cannot be called from a
    running event loop").

    To address this issue, we add a check for the event loop here. If the current thread already has an
    event loop, we run _exec_batch in a new thread; otherwise, we run it in the current thread.
    """
    if _has_running_loop():
        with ThreadPoolExecutor(1) as executor:
            return executor.submit(lambda: asyncio.run(async_func(*args, **kwargs))).result()
    else:
        return asyncio.run(async_func(*args, **kwargs))
