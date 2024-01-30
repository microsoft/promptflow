# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import os
from pathlib import Path

from fastapi import APIRouter, Request

from promptflow._core.operation_context import OperationContext
from promptflow.executor._service.contracts.execution_request import FlowExecutionRequest, NodeExecutionRequest
from promptflow.executor._service.utils.service_utils import get_log_context
from promptflow.executor.flow_executor import FlowExecutor, execute_flow
from promptflow.storage._run_storage import DefaultRunStorage

router = APIRouter()


@router.post("/execution/flow")
async def flow_execution(request: Request, flow_request: FlowExecutionRequest):
    OperationContext.get_instance().update(dict(request.headers))
    # validate request
    flow_request.validate_request()
    # resolve environment variables
    if isinstance(flow_request.environment_variables, dict):
        os.environ.update(flow_request.environment_variables)
    # execute flow
    storage = DefaultRunStorage(base_dir=flow_request.working_dir, sub_dir=flow_request.output_dir)
    with get_log_context(flow_request):
        return execute_flow(
            Path(flow_request.flow_file),
            Path(flow_request.working_dir),
            flow_request.output_dir,
            flow_request.connections,
            flow_request.inputs,
            run_id=flow_request.run_id,
            storage=storage,
        )


@router.post("/execution/node")
async def node_execution(request: Request, node_request: NodeExecutionRequest):
    OperationContext.get_instance().update(dict(request.headers))
    # validate request
    node_request.validate_request()
    # resolve environment variables
    if isinstance(node_request.environment_variables, dict):
        os.environ.update(node_request.environment_variables)
    # execute node
    with get_log_context(node_request):
        storage = DefaultRunStorage(base_dir=node_request.working_dir, sub_dir=node_request.output_dir)
        result = FlowExecutor.load_and_exec_node(
            Path(node_request.flow_file),
            node_request.node_name,
            flow_inputs=node_request.flow_inputs,
            dependency_nodes_outputs=node_request.dependency_nodes_outputs,
            connections=node_request.connections,
            working_dir=node_request.working_dir,
            storage=storage,
        )
        return result
