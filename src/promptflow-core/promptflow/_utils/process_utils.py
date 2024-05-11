# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import logging
import os
import signal

import psutil

from promptflow._utils.logger_utils import bulk_logger


def block_terminate_signal_to_parent():
    """
    In uvicorn app, the main process listens for requests and handles graceful shutdowns through
    signal listeners set up at initialization. These listeners use a file descriptor for event notifications.

    However, when a child process is forked within the application, it inherits this file descriptor,
    leading to an issue where signals sent to terminate the child process are also intercepted by the main process,
    causing an unintended shutdown of the entire application.

    To avoid this, we should return the default behavior of signal handlers for child process and call
    signal.set_wakeup_fd(-1) in the child process to prevent it from using the parent's file descriptor
    and avoiding unintended shutdowns of the main process.

    References: https://github.com/tiangolo/fastapi/discussions/7442
    """
    signal.set_wakeup_fd(-1)

    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    signal.signal(signal.SIGINT, signal.default_int_handler)


def get_available_max_worker_count(logger: logging.Logger = bulk_logger):
    """
    When creating processes using the spawn method, it consumes certain resources.
    So we can use this method to determine how many workers can be maximally created.
    """
    pid = os.getpid()
    mem_info = psutil.virtual_memory()
    available_memory = mem_info.available / (1024 * 1024)  # in MB
    process = psutil.Process(pid)
    process_memory_info = process.memory_info()
    process_memory = process_memory_info.rss / (1024 * 1024)  # in MB
    estimated_available_worker_count = int(available_memory // process_memory)
    if estimated_available_worker_count < 1:
        # TODO: For the case of vector db, Optimize execution logic
        # 1. Let the main process not consume memory because it does not actually invoke
        # 2. When the degree of parallelism is 1, main process executes the task directly
        #    and not create the child process
        logger.warning(
            f"Current system's available memory is {available_memory}MB, less than the memory "
            f"{process_memory}MB required by the process. The maximum available worker count is 1."
        )
        estimated_available_worker_count = 1
    else:
        logger.info(
            f"Current system's available memory is {available_memory}MB, "
            f"memory consumption of current process is {process_memory}MB, "
            f"estimated available worker count is {available_memory}/{process_memory} "
            f"= {estimated_available_worker_count}"
        )
    return estimated_available_worker_count


def log_errors_from_file(log_path):
    try:
        with open(log_path, "r") as f:
            error_logs = "".join(f.readlines())
            bulk_logger.error(error_logs)
        return True
    except FileNotFoundError:
        return False


def get_subprocess_log_path(index):
    from promptflow.executor._process_manager import ProcessPoolConstants

    logName_i = "{}_{}.log".format(ProcessPoolConstants.PROCESS_LOG_NAME, index)
    return ProcessPoolConstants.PROCESS_LOG_PATH / logName_i


def get_manager_process_log_path():
    from promptflow.executor._process_manager import ProcessPoolConstants

    return ProcessPoolConstants.PROCESS_LOG_PATH / ProcessPoolConstants.MANAGER_PROCESS_LOG_NAME
