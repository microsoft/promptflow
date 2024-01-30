# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import asyncio
import contextlib
import json
import multiprocessing
import os
from multiprocessing import Queue
from typing import Callable

from promptflow._core.operation_context import OperationContext
from promptflow._utils.exception_utils import ExceptionPresenter, JsonSerializedPromptflowException
from promptflow._utils.logger_utils import logger
from promptflow.executor._service.contracts.execution_request import BaseExecutionRequest
from promptflow.executor._service.utils.service_utils import get_log_context


async def invoke_function_in_process(request: BaseExecutionRequest, context_dict: dict, target_function: Callable):
    with multiprocessing.Manager() as manager:
        return_dict = manager.dict()
        exception_queue = manager.Queue()
        parent_pid = os.getpid()
        p = multiprocessing.Process(
            target=execute_function,
            args=(target_function, parent_pid, request, return_dict, exception_queue, context_dict),
        )
        p.start()
        p.join()

        if p.exitcode and p.exitcode > 0:
            exception = None
            try:
                exception = exception_queue.get(timeout=10)
            except Exception:
                pass
            # JsonSerializedPromptflowException will be raised here
            # no need to change to PromptflowException since it will be handled in app.exception_handler
            if exception is not None:
                raise exception

        default_result = {}
        result = return_dict.get("result", default_result)
        return result


def execute_function(
    execute_flow_func: Callable,
    parent_pid: int,
    request: BaseExecutionRequest,
    return_dict: dict,
    exception_queue: Queue,
    context_dict: dict,
):
    # We need to create the event loop in a new process to run the asynchronous function
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(
        execute_function_async(execute_flow_func, parent_pid, request, return_dict, exception_queue, context_dict)
    )
    loop.close()


async def execute_function_async(
    execute_flow_func: Callable,
    parent_pid: int,
    request: BaseExecutionRequest,
    return_dict: dict,
    exception_queue: Queue,
    context_dict: dict,
):
    OperationContext.get_instance().update(context_dict)
    with exception_wrapper(exception_queue):
        with get_log_context(request):
            logger.info("[%s--%s] Start processing request in executor service......", parent_pid, os.getpid())
            result = await execute_flow_func(request)
            return_dict["result"] = result


@contextlib.contextmanager
def exception_wrapper(exception_queue: Queue):
    """Wrap the exception to a generic exception to avoid the pickle error."""
    try:
        yield
    except Exception as e:
        # func runs in a child process, any customized exception can't have extra arguments other than message
        # wrap the exception to a generic exception to avoid the pickle error
        # Ref: https://bugs.python.org/issue32696
        exception_dict = ExceptionPresenter.create(e).to_dict(include_debug_info=True)
        message = json.dumps(exception_dict)
        exception = JsonSerializedPromptflowException(message=message)
        exception_queue.put(exception)
        raise exception from e
