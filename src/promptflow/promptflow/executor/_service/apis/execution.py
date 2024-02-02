# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from fastapi import APIRouter, Request

from promptflow._core.operation_context import OperationContext
from promptflow._utils.logger_utils import service_logger
from promptflow.executor._service.contracts.execution_request import FlowExecutionRequest, NodeExecutionRequest
from promptflow.executor._service.utils.process_utils import invoke_function_in_process
from promptflow.executor._service.utils.service_utils import (
    get_executor_version,
    get_service_log_context,
    set_environment_variables,
    update_operation_context,
)
from promptflow.executor.flow_executor import FlowExecutor, execute_flow
from promptflow.storage._run_storage import DefaultRunStorage

router = APIRouter(prefix="/execution")


@router.post("/flow")
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


@router.post("/node")
async def node_execution(request: Request, node_request: NodeExecutionRequest):
    update_operation_context(dict(request.headers))
    request_id = OperationContext.get_instance().request_id
    executor_version = get_executor_version()
    with get_service_log_context(node_request):
        service_logger.info(
            f"Received node execution request, node name: {node_request.node_name}, "
            f"request id: {request_id}, executor version: {executor_version}."
        )
        try:
            result = await invoke_function_in_process(node_request, request.headers, single_node_run)
            service_logger.info(f"Completed node execution request, node name: {node_request.node_name}.")
            return result
        except Exception as ex:
            error_type_and_message = (f"({ex.__class__.__name__}) {ex}",)
            service_logger.error(
                f"Failed to execute node, node name: {node_request.node_name}. Error: {error_type_and_message}"
            )
            raise ex


async def flow_test(flow_request: FlowExecutionRequest):
    # validate request
    flow_request.validate_request()
    # resolve environment variables
    set_environment_variables(flow_request)
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


async def single_node_run(node_request: NodeExecutionRequest):
    # validate request
    node_request.validate_request()
    # resolve environment variables
    set_environment_variables(node_request)
    storage = DefaultRunStorage(base_dir=node_request.working_dir, sub_dir=node_request.output_dir)
    result = FlowExecutor.load_and_exec_node(
        node_request.flow_file,
        node_request.node_name,
        flow_inputs=node_request.flow_inputs,
        dependency_nodes_outputs=node_request.dependency_nodes_outputs,
        connections=node_request.connections,
        working_dir=node_request.working_dir,
        storage=storage,
    )
    return result
