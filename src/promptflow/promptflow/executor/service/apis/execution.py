# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import asyncio
import multiprocessing
import os
from multiprocessing import Queue
from pathlib import Path
from typing import Callable

from fastapi import APIRouter, Request

from promptflow._core.operation_context import OperationContext
from promptflow._utils.logger_utils import logger
from promptflow._utils.service_utils import get_log_context, multi_processing_exception_wrapper

# from promptflow.contracts.flow import Flow
from promptflow.executor.flow_executor import execute_flow
from promptflow.executor.service.contracts.execution_request import BaseExecutionRequest, FlowExecutionRequest
from promptflow.storage._run_storage import DefaultRunStorage

router = APIRouter()


@router.post("/execution/flow")
async def flow_execution(request: Request, flow_request: FlowExecutionRequest):
    return await execute_request_in_child_process(flow_request, request.headers)


async def execute_request_in_child_process(flow_request: FlowExecutionRequest, context_dict: dict):
    with multiprocessing.Manager() as manager:
        return_dict = manager.dict()
        exception_queue = manager.Queue()
        parent_pid = os.getpid()
        p = multiprocessing.Process(
            target=execute_request,
            args=(execute_flow_in_child_process, parent_pid, flow_request, return_dict, exception_queue, context_dict),
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


async def execute_flow_in_child_process(flow_request: FlowExecutionRequest):
    # resolve environment variables
    if isinstance(flow_request.environment_variables, dict):
        os.environ.update(flow_request.environment_variables)
    # execute flow
    storage = DefaultRunStorage(base_dir=flow_request.working_dir, sub_dir=flow_request.output_dir)
    return execute_flow(
        Path(flow_request.flow_file),
        Path(flow_request.working_dir),
        flow_request.output_dir,
        flow_request.connections,
        flow_request.inputs,
        run_id=flow_request.run_id,
        storage=storage,
    )


def execute_request(
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
        execute_request_async(execute_flow_func, parent_pid, request, return_dict, exception_queue, context_dict)
    )
    loop.close()


async def execute_request_async(
    execute_flow_func: Callable,
    parent_pid: int,
    request: BaseExecutionRequest,
    return_dict: dict,
    exception_queue: Queue,
    context_dict: dict,
):
    operation_context = OperationContext.get_instance()
    operation_context.update(context_dict)
    with multi_processing_exception_wrapper(exception_queue):
        with get_log_context(request):
            logger.info("[%s--%s] Start processing request in executor service......", parent_pid, os.getpid())
            result = await execute_flow_func(request)
            return_dict["result"] = result
