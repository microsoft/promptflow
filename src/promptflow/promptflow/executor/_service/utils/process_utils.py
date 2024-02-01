# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import asyncio
import contextlib
import json
import multiprocessing
import os
from datetime import timedelta
from multiprocessing import Queue
from typing import Callable

from promptflow._core._errors import UnexpectedError
from promptflow._core.operation_context import OperationContext
from promptflow._utils.exception_utils import ExceptionPresenter, JsonSerializedPromptflowException
from promptflow._utils.logger_utils import service_logger
from promptflow.exceptions import ErrorTarget
from promptflow.executor._service._errors import ExecutionTimeoutError
from promptflow.executor._service.contracts.execution_request import BaseExecutionRequest
from promptflow.executor._service.utils.service_utils import get_log_context

EXECUTION_TIMEOUT = timedelta(days=1).total_seconds()
WAIT_SUBPROCESS_EXCEPTION_TIMEOUT = 10  # seconds


async def invoke_function_in_process(request: BaseExecutionRequest, context_dict: dict, target_function: Callable):
    with multiprocessing.Manager() as manager:
        return_dict = manager.dict()
        exception_queue = manager.Queue()

        p = multiprocessing.Process(
            target=execute_function,
            args=(target_function, request, return_dict, exception_queue, context_dict),
        )
        p.start()
        service_logger.info(f"[{os.getpid()}--{p.pid}] Start process to execute the request.")

        # Wait for the process to finish or timeout
        p.join(timeout=EXECUTION_TIMEOUT)

        # Terminate the process if it is still alive after timeout
        if p.is_alive():
            service_logger.error(f"[{p.pid}] Stop process for exceeding {EXECUTION_TIMEOUT} seconds.")
            p.terminate()
            p.join()
            raise ExecutionTimeoutError(EXECUTION_TIMEOUT)

        # Raise exception if the process exit code is not 0
        if p.exitcode and p.exitcode > 0:
            exception = None
            try:
                exception = exception_queue.get(timeout=WAIT_SUBPROCESS_EXCEPTION_TIMEOUT)
            except Exception:
                pass
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


def execute_function(
    target_function: Callable,
    request: BaseExecutionRequest,
    return_dict: dict,
    exception_queue: Queue,
    context_dict: dict,
):
    # Create the event loop in a new process to run the asynchronous function
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(
        execute_function_async(target_function, request, return_dict, exception_queue, context_dict)
    )
    loop.close()


async def execute_function_async(
    target_function: Callable,
    request: BaseExecutionRequest,
    return_dict: dict,
    exception_queue: Queue,
    context_dict: dict,
):
    OperationContext.get_instance().update(context_dict)
    with exception_wrapper(exception_queue):
        with get_log_context(request):
            service_logger.info("Start processing request in executor service...")
            result = await target_function(request)
            return_dict["result"] = result


@contextlib.contextmanager
def exception_wrapper(exception_queue: Queue):
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
        exception_queue.put(exception)
        raise exception from e
