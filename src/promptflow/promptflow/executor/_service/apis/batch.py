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
from promptflow.executor._service.utils.batch_coordinator import BatchCoordinator
from promptflow.executor._service.utils.service_utils import (
    get_log_context,
    set_environment_variables,
    update_and_get_operation_context,
)
from promptflow.storage._executor_service_storage import ExecutorServiceStorage

router = APIRouter()


@router.post("/initialize")
def initialize(request: InitializationRequest):
    with get_log_context(request, enable_service_logger=True):
        request.validate_request()
        operation_context = update_and_get_operation_context(request.operation_context)
        service_logger.info(f"Received batch init request, executor version: {operation_context.get_user_agent()}.")
        # resolve environment variables
        set_environment_variables(request.environment_variables)

        # init flow executor and validate flow
        storage = ExecutorServiceStorage(request.output_dir)
        flow_executor = FlowExecutor.create(
            request.flow_file, request.connections, request.working_dir, storage=storage, raise_ex=False
        )

        # init line process pool
        batch_coordinator = BatchCoordinator(
            request.output_dir,
            flow_executor,
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
    BatchCoordinator.get_instance().shutdown()
    return {"status": "finalized"}
