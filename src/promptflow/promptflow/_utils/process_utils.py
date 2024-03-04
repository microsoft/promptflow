# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import logging
import multiprocessing
import os
import signal

from promptflow._utils.logger_utils import bulk_logger


def block_terminate_signal_to_parent():
    # In uvicorn app, the main process listens for requests and handles graceful shutdowns through
    # signal listeners set up at initialization. These listeners use a file descriptor for event notifications.

    # However, when a child process is forked within the application, it inherits this file descriptor,
    # leading to an issue where signals sent to terminate the child process are also intercepted by the main process,
    # causing an unintended shutdown of the entire application.

    # To avoid this, we should return the default behavior of signal handlers for child process and call
    # signal.set_wakeup_fd(-1) in the child process to prevent it from using the parent's file descriptor
    # and avoiding unintended shutdowns of the main process.

    # References: https://github.com/tiangolo/fastapi/discussions/7442
    signal.set_wakeup_fd(-1)

    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    signal.signal(signal.SIGINT, signal.SIG_DFL)


def use_fork_for_process(logger: logging.Logger = bulk_logger):
    """Determines whether to use the fork method for starting a new process."""

    multiprocessing_start_method = os.environ.get("PF_BATCH_METHOD", multiprocessing.get_start_method())
    sys_start_methods = multiprocessing.get_all_start_methods()
    if multiprocessing_start_method not in sys_start_methods:
        logger.warning(
            f"Failed to set start method to '{multiprocessing_start_method}', "
            f"start method {multiprocessing_start_method} is not in: {sys_start_methods}."
        )
        logger.info(f"Set start method to default {multiprocessing.get_start_method()}.")
        multiprocessing_start_method = multiprocessing.get_start_method()
    return multiprocessing_start_method in ["fork", "forkserver"]
