# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
# this file is a middle layer between the local SDK and executor.
import contextlib
import logging
from pathlib import Path
from types import GeneratorType
from typing import Any, Mapping, Union

from promptflow._internal import ConnectionManager
from promptflow._sdk._constants import PROMPT_FLOW_DIR_NAME
from promptflow._sdk._utils import dump_flow_result, parse_variant
from promptflow._sdk.entities._flow import FlowContext, ProtectedFlow
from promptflow._sdk.operations._local_storage_operations import LoggerOperations
from promptflow._utils.context_utils import _change_working_dir
from promptflow._utils.exception_utils import ErrorResponse
from promptflow._utils.multimedia_utils import persist_multimedia_data
from promptflow.batch._csharp_executor_proxy import CSharpExecutorProxy
from promptflow.contracts.flow import Flow as ExecutableFlow
from promptflow.contracts.run_info import Status
from promptflow.exceptions import UserErrorException
from promptflow.executor._result import LineResult
from promptflow.storage._run_storage import DefaultRunStorage

from ..._utils.async_utils import async_run_allowing_running_loop
from ..._utils.logger_utils import get_cli_sdk_logger
from ..entities._eager_flow import EagerFlow
from .utils import (
    SubmitterHelper,
    print_chat_output,
    resolve_generator,
    show_node_log_and_output,
    variant_overwrite_context,
)

logger = get_cli_sdk_logger()


class TestSubmitter:
    def __init__(self, flow: Union[ProtectedFlow, EagerFlow], flow_context: FlowContext, client=None):
        self.flow = flow
        self.func = flow.entry if isinstance(flow, EagerFlow) else None
        self._origin_flow = flow
        self._dataplane_flow = None
        self.flow_context = flow_context
        # TODO: remove this
        self._variant = flow_context.variant
        from .._pf_client import PFClient

        self._client = client if client else PFClient()

    @property
    def dataplane_flow(self):
        if not self._dataplane_flow:
            self._dataplane_flow = ExecutableFlow.from_yaml(flow_file=self.flow.path, working_dir=self.flow.code)
        return self._dataplane_flow

    @contextlib.contextmanager
    def init(self):
        if isinstance(self.flow, EagerFlow):
            flow_content_manager = self._eager_flow_init
        else:
            flow_content_manager = self._dag_flow_init
        with flow_content_manager() as submitter:
            yield submitter

    @contextlib.contextmanager
    def _eager_flow_init(self):
        # no variant overwrite for eager flow
        # no connection overwrite for eager flow
        # TODO(2897147): support additional includes
        with _change_working_dir(self.flow.code):
            self._tuning_node = None
            self._node_variant = None
            yield self
            self._dataplane_flow = None

    @contextlib.contextmanager
    def _dag_flow_init(self):
        if self.flow_context.variant:
            tuning_node, node_variant = parse_variant(self.flow_context.variant)
        else:
            tuning_node, node_variant = None, None

        with variant_overwrite_context(
            flow_path=self._origin_flow.code,
            tuning_node=tuning_node,
            variant=node_variant,
            connections=self.flow_context.connections,
            overrides=self.flow_context.overrides,
        ) as temp_flow:
            # TODO execute flow test in a separate process.
            with _change_working_dir(temp_flow.code):
                self.flow = temp_flow
                self._tuning_node = tuning_node
                self._node_variant = node_variant
                yield self
                self.flow = self._origin_flow
                self._dataplane_flow = None
                self._tuning_node = None
                self._node_variant = None

    def resolve_data(
        self, node_name: str = None, inputs: dict = None, chat_history_name: str = None, dataplane_flow=None
    ):
        """
        Resolve input to flow/node test inputs.
        Raise user error when missing required inputs. And log warning when unknown inputs appeared.

        :param node_name: Node name.
        :type node_name: str
        :param inputs: Inputs of flow/node test.
        :type inputs: dict
        :param chat_history_name: Chat history name.
        :type chat_history_name: str
        :return: Dict of flow inputs, Dict of reference node output.
        :rtype: dict, dict
        """
        from promptflow.contracts.flow import InputValueType

        # TODO: only store dataplane flow in context resolver
        dataplane_flow = dataplane_flow or self.dataplane_flow
        inputs = (inputs or {}).copy()
        flow_inputs, dependency_nodes_outputs, merged_inputs = {}, {}, {}
        missing_inputs = []
        # Using default value of inputs as flow input
        if node_name:
            node = next(filter(lambda item: item.name == node_name, dataplane_flow.nodes), None)
            if not node:
                raise UserErrorException(f"Cannot find {node_name} in the flow.")
            for name, value in node.inputs.items():
                if value.value_type == InputValueType.NODE_REFERENCE:
                    input_name = (
                        f"{value.value}.{value.section}.{value.property}"
                        if value.property
                        else f"{value.value}.{value.section}"
                    )
                    if input_name in inputs:
                        dependency_input = inputs.pop(input_name)
                    elif name in inputs:
                        dependency_input = inputs.pop(name)
                    else:
                        missing_inputs.append(name)
                        continue
                    if value.property:
                        dependency_nodes_outputs[value.value] = dependency_nodes_outputs.get(value.value, {})
                        if value.property in dependency_input:
                            dependency_nodes_outputs[value.value][value.property] = dependency_input[value.property]
                    else:
                        dependency_nodes_outputs[value.value] = dependency_input
                    merged_inputs[name] = dependency_input
                elif value.value_type == InputValueType.FLOW_INPUT:
                    input_name = f"{value.prefix}{value.value}"
                    if input_name in inputs:
                        flow_input = inputs.pop(input_name)
                    elif name in inputs:
                        flow_input = inputs.pop(name)
                    else:
                        flow_input = dataplane_flow.inputs[value.value].default
                        if flow_input is None:
                            missing_inputs.append(name)
                            continue
                    flow_inputs[value.value] = flow_input
                    merged_inputs[name] = flow_input
                else:
                    flow_inputs[name] = inputs.pop(name) if name in inputs else value.value
                    merged_inputs[name] = flow_inputs[name]
        else:
            for name, value in dataplane_flow.inputs.items():
                if name in inputs:
                    flow_inputs[name] = inputs.pop(name)
                    merged_inputs[name] = flow_inputs[name]
                else:
                    if value.default is None:
                        # When the flow is a chat flow and chat_history has no default value, set an empty list for it
                        if chat_history_name and name == chat_history_name:
                            flow_inputs[name] = []
                        else:
                            missing_inputs.append(name)
                    else:
                        flow_inputs[name] = value.default
                        merged_inputs[name] = flow_inputs[name]
        prefix = node_name or "flow"
        if missing_inputs:
            raise UserErrorException(f'Required input(s) {missing_inputs} are missing for "{prefix}".')
        if inputs:
            logger.warning(f"Unknown input(s) of {prefix}: {inputs}")
            flow_inputs.update(inputs)
            merged_inputs.update(inputs)
        logger.info(f"{prefix} input(s): {merged_inputs}")
        return flow_inputs, dependency_nodes_outputs

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
        from promptflow.executor import FlowExecutor

        if not connections:
            connections = SubmitterHelper.resolve_connections(flow=self.flow, client=self._client)
        credential_list = ConnectionManager(connections).get_secret_list()

        # resolve environment variables
        environment_variables = SubmitterHelper.load_and_resolve_environment_variables(
            flow=self.flow, environment_variables=environment_variables, client=self._client
        )
        environment_variables = environment_variables if environment_variables else {}
        SubmitterHelper.init_env(environment_variables=environment_variables)

        with LoggerOperations(
            file_path=self.flow.code / PROMPT_FLOW_DIR_NAME / "flow.log",
            stream=stream_log,
            credential_list=credential_list,
        ):
            storage = DefaultRunStorage(base_dir=self.flow.code, sub_dir=Path(".promptflow/intermediate"))
            flow_executor = FlowExecutor.create(
                self.flow.path, connections, self.flow.code, storage=storage, raise_ex=False, func=self.func
            )
            flow_executor.enable_streaming_for_llm_flow(lambda: stream_output)
            line_result = flow_executor.exec_line(inputs, index=0, allow_generator_output=allow_generator_output)
            line_result.output = persist_multimedia_data(
                line_result.output, base_dir=self.flow.code, sub_dir=Path(".promptflow/output")
            )
            if line_result.aggregation_inputs:
                # Convert inputs of aggregation to list type
                flow_inputs = {k: [v] for k, v in inputs.items()}
                aggregation_inputs = {k: [v] for k, v in line_result.aggregation_inputs.items()}
                aggregation_results = flow_executor.exec_aggregation(flow_inputs, aggregation_inputs=aggregation_inputs)
                line_result.node_run_infos.update(aggregation_results.node_run_infos)
                line_result.run_info.metrics = aggregation_results.metrics
            if isinstance(line_result.output, dict):
                # Remove line_number from output
                line_result.output.pop(LINE_NUMBER_KEY, None)
                generator_outputs = self._get_generator_outputs(line_result.output)
                if generator_outputs:
                    logger.info(f"Some streaming outputs in the result, {generator_outputs.keys()}")
            return line_result

    def node_test(
        self,
        node_name: str,
        flow_inputs: Mapping[str, Any],
        dependency_nodes_outputs: Mapping[str, Any],
        environment_variables: dict = None,
        stream: bool = True,
    ):
        from promptflow.executor import FlowExecutor

        connections = SubmitterHelper.resolve_connections(flow=self.flow, client=self._client)
        credential_list = ConnectionManager(connections).get_secret_list()

        # resolve environment variables
        environment_variables = SubmitterHelper.load_and_resolve_environment_variables(
            flow=self.flow, environment_variables=environment_variables, client=self._client
        )
        SubmitterHelper.init_env(environment_variables=environment_variables)

        with LoggerOperations(
            file_path=self.flow.code / PROMPT_FLOW_DIR_NAME / f"{node_name}.node.log",
            stream=stream,
            credential_list=credential_list,
        ):
            storage = DefaultRunStorage(base_dir=self.flow.code, sub_dir=Path(".promptflow/intermediate"))
            result = FlowExecutor.load_and_exec_node(
                self.flow.path,
                node_name,
                flow_inputs=flow_inputs,
                dependency_nodes_outputs=dependency_nodes_outputs,
                connections=connections,
                working_dir=self.flow.code,
                storage=storage,
            )
            return result

    def _chat_flow(self, inputs, chat_history_name, environment_variables: dict = None, show_step_output=False):
        """
        Interact with Chat Flow. Do the following:
            1. Combine chat_history and user input as the input for each round of the chat flow.
            2. Each round of chat is executed once flow test.
            3. Prefix the output for distinction.
        """
        from colorama import Fore, init

        @contextlib.contextmanager
        def change_logger_level(level):
            origin_level = logger.level
            logger.setLevel(level)
            yield
            logger.setLevel(origin_level)

        init(autoreset=True)
        chat_history = []
        generator_record = {}
        input_name = next(
            filter(lambda key: self.dataplane_flow.inputs[key].is_chat_input, self.dataplane_flow.inputs.keys())
        )
        output_name = next(
            filter(
                lambda key: self.dataplane_flow.outputs[key].is_chat_output,
                self.dataplane_flow.outputs.keys(),
            )
        )

        # Pass connections to avoid duplicate calculation (especially http call)
        connections = SubmitterHelper.resolve_connections(flow=self.flow, client=self._client)
        while True:
            try:
                print(f"{Fore.GREEN}User: ", end="")
                input_value = input()
                if not input_value.strip():
                    continue
            except (KeyboardInterrupt, EOFError):
                print("Terminate the chat.")
                break
            inputs = inputs or {}
            inputs[input_name] = input_value
            inputs[chat_history_name] = chat_history
            with change_logger_level(level=logging.WARNING):
                chat_inputs, _ = self.resolve_data(inputs=inputs)

            flow_result = self.flow_test(
                inputs=chat_inputs,
                environment_variables=environment_variables,
                stream_log=False,
                allow_generator_output=True,
                connections=connections,
                stream_output=True,
            )
            self._raise_error_when_test_failed(flow_result, show_trace=True)
            show_node_log_and_output(flow_result.node_run_infos, show_step_output, generator_record)

            print(f"{Fore.YELLOW}Bot: ", end="")
            print_chat_output(flow_result.output[output_name], generator_record)
            flow_result = resolve_generator(flow_result, generator_record)
            flow_outputs = {k: v for k, v in flow_result.output.items()}
            history = {"inputs": {input_name: input_value}, "outputs": flow_outputs}
            chat_history.append(history)
            dump_flow_result(flow_folder=self._origin_flow.code, flow_result=flow_result, prefix="chat")

    @staticmethod
    def _raise_error_when_test_failed(test_result, show_trace=False):
        from promptflow.executor._result import LineResult

        test_status = test_result.run_info.status if isinstance(test_result, LineResult) else test_result.status

        if test_status == Status.Failed:
            error_dict = test_result.run_info.error if isinstance(test_result, LineResult) else test_result.error
            error_response = ErrorResponse.from_error_dict(error_dict)
            user_execution_error = error_response.get_user_execution_error_info()
            error_message = error_response.message
            stack_trace = user_execution_error.get("traceback", "")
            error_type = user_execution_error.get("type", "Exception")
            if show_trace:
                print(stack_trace)
            raise UserErrorException(f"{error_type}: {error_message}")

    @staticmethod
    def _get_generator_outputs(outputs):
        outputs = outputs or {}
        return {key: outputs for key, output in outputs.items() if isinstance(output, GeneratorType)}


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
        environment_variables = SubmitterHelper.load_and_resolve_environment_variables(
            flow=self.flow, environment_variables=environment_variables, client=self._client
        )
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
