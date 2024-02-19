# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import asyncio
import contextlib
import json
import multiprocessing
import os
from datetime import timedelta
from typing import Callable

from promptflow._core._errors import UnexpectedError
from promptflow._core.operation_context import OperationContext
from promptflow._utils.exception_utils import ExceptionPresenter, JsonSerializedPromptflowException
from promptflow._utils.logger_utils import service_logger
from promptflow.exceptions import ErrorTarget
from promptflow.executor._service._errors import ExecutionTimeoutError
from promptflow.executor._service.utils.service_utils import get_log_context

LONG_WAIT_TIMEOUT = timedelta(days=1).total_seconds()
SHORT_WAIT_TIMEOUT = 10


async def invoke_sync_function_in_process(
    request, context_dict: dict, target_function: Callable, wait_timeout: int = LONG_WAIT_TIMEOUT
):
    with multiprocessing.Manager() as manager:
        return_dict = manager.dict()
        error_dict = manager.dict()

        p = multiprocessing.Process(
            target=execute_target_function,
            args=(target_function, request, return_dict, error_dict, context_dict),
        )
        p.start()
        service_logger.info(f"[{os.getpid()}--{p.pid}] Start process to execute the request.")

        # Wait for the process to finish or timeout asynchronously
        try:
            await asyncio.wait_for(asyncio.to_thread(p.join), timeout=wait_timeout)
        except asyncio.TimeoutError:
            # Terminate the process if it is still alive after timeout
            if p.is_alive():
                service_logger.error(f"[{p.pid}] Stop process for exceeding {wait_timeout} seconds.")
                p.terminate()
                p.join()
                raise ExecutionTimeoutError(wait_timeout)

        # Raise exception if the process exit code is not 0
        if p.exitcode != 0:
            exception = error_dict.get("error", None)
            if exception is None:
                raise UnexpectedError(
                    message="Unexpected error occurred while executing the request",
                    target=ErrorTarget.EXECUTOR,
                )
            # JsonSerializedPromptflowException will be raised here
            # no need to change to PromptflowException since it will be handled in app.exception_handler
            raise exception

        service_logger.info(f"[{p.pid}] Process finished.")
        return return_dict.get("result", {})


def execute_target_function(
    target_function: Callable,
    request,
    return_dict: dict,
    error_dict: dict,
    context_dict: dict,
):
    OperationContext.get_instance().update(context_dict)
    with exception_wrapper(error_dict):
        with get_log_context(request):
            service_logger.info("Start processing request in executor service...")
            result = target_function(request)
            return_dict["result"] = result


@contextlib.contextmanager
def exception_wrapper(error_dict: dict):
    """Wrap the exception to a generic exception to avoid the pickle error."""
    try:
        yield
    except Exception as e:
        # Func runs in a child process, any customized exception can't have extra arguments other than message
        # Wrap the exception to a generic exception to avoid the pickle error
        # Ref: https://bugs.python.org/issue32696
        exception_dict = ExceptionPresenter.create(e).to_dict(include_debug_info=True)
        message = json.dumps(exception_dict)
        exception = JsonSerializedPromptflowException(message=message)
        error_dict["error"] = exception
        raise exception from e
