# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from fastapi import APIRouter

from promptflow._utils.logger_utils import service_logger
from promptflow.executor import FlowExecutor
from promptflow.executor._service.contracts.batch_request import (
    AggregationRequest,
    InitializationRequest,
    LineExecutionRequest,
)
from promptflow.executor._service.utils.service_utils import (
    get_log_context,
    set_environment_variables,
    update_and_get_operation_context,
)

router = APIRouter()


@router.post("/initialize")
async def initialize(request: InitializationRequest):
    with get_log_context(request, enable_service_logger=True):
        request.validate_request()
        operation_context = update_and_get_operation_context(request.operation_context)
        service_logger.info(
            f"Received batch init request, total lines: {request.line_count}, "
            f"executor version: {operation_context.get_user_agent()}."
        )
        # resolve environment variables
        set_environment_variables(request.environment_variables)

        # init flow executor and validate flow
        # storage = ...????
        flow_executor = FlowExecutor.create(request.flow_file, request.connections, request.working_dir, raise_ex=False)
        print(flow_executor)

        # init line process pool

        # return json response
        return {"status": "initialized"}


@router.post("/execution")
async def execution(request: LineExecutionRequest):
    # get pool

    # submit a run

    # return line result

    pass


@router.post("/aggregation")
async def aggregation(request: AggregationRequest):
    pass


@router.post("/finalize")
async def finalize():
    pass
