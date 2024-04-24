# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import asyncio
import contextlib
import json
import multiprocessing
import os
from datetime import datetime, timedelta
from typing import Any, Callable, Mapping

from promptflow._core._errors import UnexpectedError
from promptflow._utils.exception_utils import ExceptionPresenter, JsonSerializedPromptflowException
from promptflow._utils.logger_utils import service_logger
from promptflow._utils.process_utils import block_terminate_signal_to_parent
from promptflow.exceptions import ErrorTarget
from promptflow.executor._service._errors import ExecutionCanceledError, ExecutionTimeoutError
from promptflow.executor._service.utils.process_manager import ProcessManager
from promptflow.executor._service.utils.service_utils import set_environment_variables
from promptflow.tracing._operation_context import OperationContext

LONG_WAIT_TIMEOUT = timedelta(days=1).total_seconds()
SHORT_WAIT_TIMEOUT = 10


async def invoke_sync_function_in_process(
    target_function: Callable,
    *,
    args: tuple = (),
    kwargs: dict = {},
    run_id: str = None,
    context_dict: dict = None,
    wait_timeout: int = LONG_WAIT_TIMEOUT,
    environment_variables: Mapping[str, Any] = None,
):
    with multiprocessing.Manager() as manager:
        return_dict = manager.dict()
        error_dict = manager.dict()

        p = multiprocessing.Process(
            target=_execute_target_function,
            args=(target_function, args, kwargs, return_dict, error_dict, context_dict, environment_variables),
        )
        p.start()
        service_logger.info(f"[{os.getpid()}--{p.pid}] Start process to execute the request.")
        if run_id:
            ProcessManager().start_process(run_id, p)

        try:
            # Wait for the process to finish or timeout asynchronously
            start_time = datetime.utcnow()
            while (datetime.utcnow() - start_time).total_seconds() < wait_timeout and p.is_alive():
                await asyncio.sleep(1)

            # Terminate the process if it is still alive after timeout
            if p.is_alive():
                service_logger.error(f"[{p.pid}] Stop process for exceeding {wait_timeout} seconds.")
                p.terminate()
                p.join()
                raise ExecutionTimeoutError(wait_timeout)

            # Raise exception if the process exit code is not 0
            if p.exitcode != 0:
                # If process is not None, it indicates that the process has been terminated by other errors.
                exception = error_dict.get("error", None)
                if exception is None:
                    # If process is None, it indicates that the process has been terminated by cancel request.
                    if run_id and not ProcessManager().get_process(run_id):
                        raise ExecutionCanceledError(run_id)
                    raise UnexpectedError(
                        message="Unexpected error occurred while executing the request",
                        target=ErrorTarget.EXECUTOR,
                    )
                # JsonSerializedPromptflowException will be raised here
                # no need to change to PromptflowException since it will be handled in app.exception_handler
                raise exception

            service_logger.info(f"[{p.pid}--{os.getpid()}] Process finished.")
            return return_dict.get("result", {})
        finally:
            if run_id:
                ProcessManager().remove_process(run_id)


def _execute_target_function(
    target_function: Callable,
    args: tuple,
    kwargs: dict,
    return_dict: dict,
    error_dict: dict,
    context_dict: dict,
    environment_variables: Mapping[str, Any],
):
    block_terminate_signal_to_parent()
    set_environment_variables(environment_variables)
    with exception_wrapper(error_dict):
        if context_dict:
            OperationContext.get_instance().update(context_dict)
        service_logger.info("Start processing request in executor service...")
        result = target_function(*args, **kwargs)
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
