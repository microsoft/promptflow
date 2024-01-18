# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import os

from fastapi import APIRouter, Request

from promptflow._constants import LINE_NUMBER_KEY
from promptflow._utils.logger_utils import LogContext
from promptflow._utils.multimedia_utils import persist_multimedia_data
from promptflow.executor import FlowExecutor
from promptflow.executor._result import LineResult
from promptflow.executor.service.contracts.execution_request import FlowExecutionRequest, NodeExecutionRequest
from promptflow.storage._run_storage import DefaultRunStorage

router = APIRouter()


@router.post("/execution/flow")
async def flow_execution(request: Request, flow_request: FlowExecutionRequest):
    # Operation context???
    # headers = dict(request.headers)
    # get connection endpoints
    connections = {}
    credential_list = []
    # resolve environment variables
    if isinstance(flow_request.environment_variables, dict):
        os.environ.update(flow_request.environment_variables)

    with LogContext(
        file_path=flow_request.log_path,
        credential_list=credential_list,
    ):
        # init storage for persisting intermediate image datas
        storage = DefaultRunStorage(base_dir=flow_request.working_dir, sub_dir=flow_request.output_dir)
        # init flow executor
        flow_executor = FlowExecutor.create(
            flow_request.flow_file,
            connections,
            flow_request.working_dir,
            storage=storage,
            raise_ex=False,
        )
        line_result: LineResult = flow_executor.exec_line(
            flow_request.inputs,
            index=0,
            run_id=flow_request.run_id,
        )
        line_result.output = persist_multimedia_data(line_result.output, base_dir=flow_request.output_dir)
        if line_result.aggregation_inputs:
            # convert inputs of aggregation to list type
            flow_inputs = {k: [v] for k, v in flow_request.inputs.items()}
            aggregation_inputs = {k: [v] for k, v in line_result.aggregation_inputs.items()}
            aggregation_results = flow_executor.exec_aggregation(flow_inputs, aggregation_inputs=aggregation_inputs)
            line_result.node_run_infos = {**line_result.node_run_infos, **aggregation_results.node_run_infos}
            line_result.run_info.metrics = aggregation_results.metrics
        if isinstance(line_result.output, dict):
            # remove line_number from output
            line_result.output.pop(LINE_NUMBER_KEY, None)
        # TODO: need serialize line_result to json
        return line_result


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
