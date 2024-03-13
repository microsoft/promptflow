# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import os
from pathlib import Path

from fastapi import APIRouter

from promptflow._utils.logger_utils import service_logger
from promptflow.executor._service._errors import FlowFilePathInvalid
from promptflow.executor._service.contracts.batch_request import (
    AggregationRequest,
    InitializationRequest,
    LineExecutionRequest,
)
from promptflow.executor._service.utils.batch_coordinator import BatchCoordinator
from promptflow.executor._service.utils.service_utils import (
    get_log_context,
    set_environment_variables,
    update_and_get_operation_context,
)

router = APIRouter()


@router.post("/initialize")
def initialize(request: InitializationRequest):
    with get_log_context(request, enable_service_logger=True):
        # validate request and get operation context
        request.validate_request()

        # Ensure that the flow file path is within the working directory
        working_dir = os.path.normpath(request.working_dir)
        flow_file = os.path.normpath(request.flow_file)
        full_path = os.path.normpath(os.path.join(working_dir, flow_file))
        if not full_path.startswith(working_dir):
            raise FlowFilePathInvalid(
                message_format=(
                    "The flow file path ({flow_file}) is invalid. The path should be in the working directory."
                ),
                flow_file=request.flow_file.as_posix(),
            )
        request.working_dir = Path(working_dir)
        request.flow_file = Path(flow_file)

        operation_context = update_and_get_operation_context(request.operation_context)
        service_logger.info(f"Received batch init request, executor version: {operation_context.get_user_agent()}.")
        # resolve environment variables
        set_environment_variables(request)
        # init batch coordinator to validate flow and create process pool
        batch_coordinator = BatchCoordinator(
            Path(working_dir),
            Path(flow_file),
            request.output_dir,
            request.connections,
            worker_count=request.worker_count,
            line_timeout_sec=request.line_timeout_sec,
        )
        batch_coordinator.start()
        # return json response
        return {"status": "initialized"}


@router.post("/execution")
async def execution(request: LineExecutionRequest):
    return await BatchCoordinator.get_instance().exec_line(request)


@router.post("/aggregation")
def aggregation(request: AggregationRequest):
    return BatchCoordinator.get_instance().exec_aggregation(request)


@router.post("/finalize")
def finalize():
    BatchCoordinator.get_instance().close()
    return {"status": "finalized"}
