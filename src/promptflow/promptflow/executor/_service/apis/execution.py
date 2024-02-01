# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import os

from fastapi import APIRouter, Request

from promptflow._core.operation_context import OperationContext
from promptflow._utils.logger_utils import service_logger
from promptflow.executor._service.contracts.execution_request import FlowExecutionRequest
from promptflow.executor._service.utils.process_utils import invoke_function_in_process
from promptflow.executor._service.utils.service_utils import (
    get_executor_version,
    get_service_log_context,
    update_operation_context,
)
from promptflow.executor.flow_executor import execute_flow
from promptflow.storage._run_storage import DefaultRunStorage

router = APIRouter()


@router.post("/execution/flow")
async def flow_execution(request: Request, flow_request: FlowExecutionRequest):
    update_operation_context(dict(request.headers))
    request_id = OperationContext.get_instance().request_id
    executor_version = get_executor_version()
    with get_service_log_context(flow_request):
        service_logger.info(
            f"Received flow execution request, flow run id: {flow_request.run_id}, "
            f"request id: {request_id}, executor version: {executor_version}."
        )
        try:
            result = await invoke_function_in_process(flow_request, request.headers, flow_test)
            service_logger.info(f"Completed flow execution request, flow run id: {flow_request.run_id}.")
            return result
        except Exception as ex:
            error_type_and_message = (f"({ex.__class__.__name__}) {ex}",)
            service_logger.error(
                f"Failed to execute flow, flow run id: {flow_request.run_id}. Error: {error_type_and_message}"
            )
            raise ex


async def flow_test(flow_request: FlowExecutionRequest):
    # validate request
    flow_request.validate_request()
    # resolve environment variables
    if isinstance(flow_request.environment_variables, dict):
        os.environ.update(flow_request.environment_variables)
    # execute flow
    storage = DefaultRunStorage(base_dir=flow_request.working_dir, sub_dir=flow_request.output_dir)
    return execute_flow(
        flow_request.flow_file,
        flow_request.working_dir,
        flow_request.output_dir,
        flow_request.connections,
        flow_request.inputs,
        run_id=flow_request.run_id,
        storage=storage,
    )
