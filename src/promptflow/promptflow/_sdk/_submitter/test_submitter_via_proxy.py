# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
# this file is a middle layer between the local SDK and executor.
from pathlib import Path
from typing import Any, Mapping

from promptflow._internal import ConnectionManager
from promptflow._sdk._constants import PROMPT_FLOW_DIR_NAME
from promptflow._sdk.entities._flow import FlowContext, ProtectedFlow
from promptflow._sdk.operations._local_storage_operations import LoggerOperations
from promptflow._utils.multimedia_utils import persist_multimedia_data
from promptflow.batch._csharp_executor_proxy import CSharpExecutorProxy
from promptflow.executor._result import LineResult
from promptflow.storage._run_storage import DefaultRunStorage

from ..._utils.async_utils import async_run_allowing_running_loop
from ..._utils.logger_utils import get_cli_sdk_logger
from .test_submitter import TestSubmitter
from .utils import SubmitterHelper

logger = get_cli_sdk_logger()


class TestSubmitterViaProxy(TestSubmitter):
    def __init__(self, flow: ProtectedFlow, flow_context: FlowContext, client=None):
        super().__init__(flow, flow_context, client)

    def flow_test(
        self,
        inputs: Mapping[str, Any],
        environment_variables: dict = None,
        stream_log: bool = True,
        allow_generator_output: bool = False,
        connections: dict = None,  # executable connections dict, to avoid http call each time in chat mode
        stream_output: bool = True,
    ):

        from promptflow._constants import LINE_NUMBER_KEY

        if not connections:
            connections = SubmitterHelper.resolve_used_connections(
                flow=self.flow,
                tools_meta=CSharpExecutorProxy.get_tool_metadata(
                    flow_file=self.flow.flow_dag_path,
                    working_dir=self.flow.code,
                ),
                client=self._client,
            )
        credential_list = ConnectionManager(connections).get_secret_list()

        # resolve environment variables
        SubmitterHelper.resolve_environment_variables(environment_variables=environment_variables, client=self._client)
        environment_variables = environment_variables if environment_variables else {}
        SubmitterHelper.init_env(environment_variables=environment_variables)

        log_path = self.flow.code / PROMPT_FLOW_DIR_NAME / "flow.log"
        with LoggerOperations(
            file_path=log_path,
            stream=stream_log,
            credential_list=credential_list,
        ):
            try:
                storage = DefaultRunStorage(base_dir=self.flow.code, sub_dir=Path(".promptflow/intermediate"))
                flow_executor: CSharpExecutorProxy = async_run_allowing_running_loop(
                    CSharpExecutorProxy.create,
                    self.flow.path,
                    self.flow.code,
                    connections=connections,
                    storage=storage,
                    log_path=log_path,
                )

                line_result: LineResult = async_run_allowing_running_loop(
                    flow_executor.exec_line_async, inputs, index=0
                )
                line_result.output = persist_multimedia_data(
                    line_result.output, base_dir=self.flow.code, sub_dir=Path(".promptflow/output")
                )
                if line_result.aggregation_inputs:
                    # Convert inputs of aggregation to list type
                    flow_inputs = {k: [v] for k, v in inputs.items()}
                    aggregation_inputs = {k: [v] for k, v in line_result.aggregation_inputs.items()}
                    aggregation_results = async_run_allowing_running_loop(
                        flow_executor.exec_aggregation_async, flow_inputs, aggregation_inputs
                    )
                    line_result.node_run_infos.update(aggregation_results.node_run_infos)
                    line_result.run_info.metrics = aggregation_results.metrics
                if isinstance(line_result.output, dict):
                    # Remove line_number from output
                    line_result.output.pop(LINE_NUMBER_KEY, None)
                    generator_outputs = self._get_generator_outputs(line_result.output)
                    if generator_outputs:
                        logger.info(f"Some streaming outputs in the result, {generator_outputs.keys()}")
                return line_result
            finally:
                async_run_allowing_running_loop(flow_executor.destroy)

    def exec_with_inputs(self, inputs):
        from promptflow._constants import LINE_NUMBER_KEY

        connections = SubmitterHelper.resolve_used_connections(
            flow=self.flow,
            tools_meta=CSharpExecutorProxy.get_tool_metadata(
                flow_file=self.flow.path,
                working_dir=self.flow.code,
            ),
            client=self._client,
        )
        storage = DefaultRunStorage(base_dir=self.flow.code, sub_dir=Path(".promptflow/intermediate"))
        flow_executor = CSharpExecutorProxy.create(
            flow_file=self.flow.path,
            working_dir=self.flow.code,
            connections=connections,
            storage=storage,
        )

        try:
            # validate inputs
            flow_inputs, _ = self.resolve_data(inputs=inputs, dataplane_flow=self.dataplane_flow)
            line_result = async_run_allowing_running_loop(flow_executor.exec_line_async, inputs, index=0)
            # line_result = flow_executor.exec_line(inputs, index=0)
            if isinstance(line_result.output, dict):
                # Remove line_number from output
                line_result.output.pop(LINE_NUMBER_KEY, None)
            return line_result
        finally:
            flow_executor.destroy()
