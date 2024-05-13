# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------


from fastapi import APIRouter

from promptflow._utils.logger_utils import service_logger
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
        # Validate request and get operation context.
        request.validate_request()
        operation_context = update_and_get_operation_context(request.operation_context)
        service_logger.info(f"Received batch init request, executor version: {operation_context.get_user_agent()}.")
        # Resolve environment variables.
        set_environment_variables(request.environment_variables)
        # Init batch coordinator to validate flow and create process pool.
        batch_coordinator = BatchCoordinator(
            working_dir=request.working_dir,
            flow_file=request.flow_file,
            output_dir=request.output_dir,
            flow_name=request.flow_name,
            connections=request.connections,
            worker_count=request.worker_count,
            line_timeout_sec=request.line_timeout_sec,
            init_kwargs=request.init_kwargs,
        )
        batch_coordinator.start()
        # Return some flow infos including the flow inputs definition and whether it has aggregation nodes.
        return batch_coordinator.get_flow_infos()


@router.post("/execution")
async def execution(request: LineExecutionRequest):
    return await BatchCoordinator.get_instance().exec_line(request)


@router.post("/aggregation")
def aggregation(request: AggregationRequest):
    return BatchCoordinator.get_instance().exec_aggregation(request)


@router.post("/finalize")
def finalize():
    with BatchCoordinator.get_instance().get_log_context():
        service_logger.info("Received the finalize request.")
        BatchCoordinator.get_instance().close()
        return {"status": "finalized"}
