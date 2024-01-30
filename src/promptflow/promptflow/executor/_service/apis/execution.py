# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import os

from fastapi import APIRouter, Request

from promptflow.executor._service.contracts.execution_request import FlowExecutionRequest
from promptflow.executor._service.utils.process_utils import invoke_function_in_process
from promptflow.executor.flow_executor import execute_flow
from promptflow.storage._run_storage import DefaultRunStorage

router = APIRouter()


@router.post("/execution/flow")
async def flow_execution(request: Request, flow_request: FlowExecutionRequest):
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

    return await invoke_function_in_process(flow_request, request.headers, flow_test)
