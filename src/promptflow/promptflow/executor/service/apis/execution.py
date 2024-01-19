# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import os

from fastapi import APIRouter, Request

# from promptflow.contracts.flow import Flow
from promptflow._core.operation_context import OperationContext
from promptflow._utils.logger_utils import LogContext
from promptflow.executor.flow_executor import FlowExecutor, execute_flow
from promptflow.executor.service.contracts.execution_request import FlowExecutionRequest, NodeExecutionRequest
from promptflow.storage._run_storage import DefaultRunStorage

router = APIRouter()


@router.post("/execution/flow")
async def flow_execution(request: Request, flow_request: FlowExecutionRequest):
    # set operation context
    OperationContext.get_instance().update(dict(request.headers))
    # get connection endpoints
    connections = {}
    credential_list = []
    """
    flow = Flow.from_yaml(flow_request.flow_file)
    connections_set = flow.get_connection_names()
    """
    # resolve environment variables
    if isinstance(flow_request.environment_variables, dict):
        os.environ.update(flow_request.environment_variables)

    with LogContext(file_path=flow_request.log_path, credential_list=credential_list):
        storage = DefaultRunStorage(base_dir=flow_request.working_dir, sub_dir=flow_request.output_dir)
        return execute_flow(
            flow_request.flow_file,
            flow_request.working_dir,
            connections,
            flow_request.inputs,
            storage=storage,
        )


@router.post("/execution/node")
async def node_execution(request: Request, node_request: NodeExecutionRequest):
    # Operation context???
    # headers = dict(request.headers)
    # get connection endpoints
    connections = {}
    credential_list = []
    # resolve environment variables
    if isinstance(node_request.environment_variables, dict):
        os.environ.update(node_request.environment_variables)

    with LogContext(
        file_path=node_request.log_path,
        credential_list=credential_list,
    ):
        storage = DefaultRunStorage(base_dir=node_request.working_dir, sub_dir=node_request.output_dir)
        result = FlowExecutor.load_and_exec_node(
            node_request.flow_file,
            node_request.node_name,
            flow_inputs=node_request.flow_inputs,
            dependency_nodes_outputs=node_request.dependency_nodes_outputs,
            connections=connections,
            working_dir=node_request.working_dir,
            storage=storage,
        )
        # TODO: need serialize node run info to json
        return result
