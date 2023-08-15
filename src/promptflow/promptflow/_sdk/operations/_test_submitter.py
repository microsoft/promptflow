# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
# this file is a middle layer between the local SDK and executor.
import contextlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

from promptflow._sdk._constants import CHAT_HISTORY
from promptflow._sdk._utils import parse_variant
from promptflow._sdk.entities._flow import Flow
from promptflow._sdk.operations._local_storage_operations import LoggerOperations
from promptflow._sdk.operations._run_submitter import SubmitterHelper, variant_overwrite_context
from promptflow._utils.dataclass_serializer import serialize
from promptflow.contracts.flow import Flow as ExecutableFlow
from promptflow.contracts.run_info import Status
from promptflow.exceptions import ErrorResponse, UserErrorException


class TestSubmitter:
    def __init__(self, flow: Flow, variant=None):
        self.flow = flow
        self._origin_flow = flow
        self._dataplane_flow = None
        self._variant = variant

    @property
    def dataplane_flow(self):
        if not self._dataplane_flow:
            self._dataplane_flow = ExecutableFlow.from_yaml(flow_file=self.flow.path, working_dir=self.flow.code)
        return self._dataplane_flow

    @contextlib.contextmanager
    def init(self):
        if self._variant:
            tuning_node, node_variant = parse_variant(self._variant)
        else:
            tuning_node, node_variant = None, None
        with variant_overwrite_context(self._origin_flow.code, tuning_node, node_variant) as temp_flow:
            self.flow = temp_flow
            self._tuning_node = tuning_node
            self._node_variant = node_variant
            yield self
            self.flow = self._origin_flow
            self._dataplane_flow = None
            self._tuning_node = None
            self._node_variant = None

    def _resolve_data(self, node_name: str = None, inputs: dict = None):
        from promptflow.contracts.flow import InputValueType

        inputs = inputs or {}
        flow_inputs, dependency_nodes_outputs = {}, {}
        # Using default value of inputs as flow input
        if node_name:
            node = next(filter(lambda item: item.name == node_name, self.dataplane_flow.nodes), None)
            if not node:
                raise UserErrorException(f"Cannot find {node_name} in the flow.")
            for name, value in node.inputs.items():
                if value.value_type == InputValueType.NODE_REFERENCE:
                    input_name = f"{value.value}.{value.section}"
                    dependency_nodes_outputs[value.value] = inputs.get(input_name, None) or inputs.get(name, None)
                elif value.value_type == InputValueType.FLOW_INPUT:
                    input_name = f"{value.prefix}{value.value}"
                    flow_inputs[value.value] = (
                        inputs.get(input_name, None)
                        or inputs.get(name, None)
                        or self.dataplane_flow.inputs[value.value].default
                    )
                else:
                    flow_inputs[name] = inputs[name] if name in inputs else value.value
        else:
            for name, value in self.dataplane_flow.inputs.items():
                flow_inputs[name] = inputs[name] if name in inputs else value.default
        return flow_inputs, dependency_nodes_outputs

    def flow_test(self, inputs: Mapping[str, Any], environment_variables: dict = None, stream: bool = True):
        from promptflow.executor.flow_executor import LINE_NUMBER_KEY, FlowExecutor

        connections = SubmitterHelper.resolve_connections(flow=self.flow)
        # resolve environment variables
        SubmitterHelper.resolve_environment_variables(environment_variables=environment_variables)
        environment_variables = environment_variables if environment_variables else {}
        SubmitterHelper.init_env(environment_variables=environment_variables)

        with LoggerOperations(log_path=self.flow.code / ".promptflow" / "flow.log").setup_logger(stream=stream):
            flow_executor = FlowExecutor.create(self.flow.path, connections, self.flow.code, raise_ex=False)
            line_result = flow_executor.exec_line(inputs, index=0)
            if line_result.aggregation_inputs:
                # Convert inputs of aggregation to list type
                flow_inputs = {k: [v] for k, v in inputs.items()}
                aggregation_inputs = {k: [v] for k, v in line_result.aggregation_inputs.items()}
                aggr_results = flow_executor.exec_aggregation(flow_inputs, aggregation_inputs=aggregation_inputs)
                line_result.node_run_infos.update(aggr_results.node_run_infos)
                line_result.run_info.metrics = aggr_results.metrics
            if isinstance(line_result.output, dict):
                # Remove line_number from output
                line_result.output.pop(LINE_NUMBER_KEY, None)
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

        connections = SubmitterHelper.resolve_connections(flow=self.flow)
        # resolve environment variables
        SubmitterHelper.resolve_environment_variables(environment_variables=environment_variables)
        SubmitterHelper.init_env(environment_variables=environment_variables)

        with LoggerOperations(log_path=self.flow.code / ".promptflow" / f"{node_name}.node.log").setup_logger(
            stream=stream
        ):
            result = FlowExecutor.load_and_exec_node(
                self.flow.path,
                node_name,
                flow_inputs=flow_inputs,
                dependency_nodes_outputs=dependency_nodes_outputs,
                connections=connections,
                working_dir=self.flow.code,
            )
            return result

    def _chat_flow(self, inputs, environment_variables: dict = None, show_step_output=False):
        """
        Interact with Chat Flow. Do the following:
            1. Combine chat_history and user input as the input for each round of the chat flow.
            2. Each round of chat is executed once flow test.
            3. Perfix the output for distinction.
        """
        from colorama import Fore, init

        @contextlib.contextmanager
        def add_prefix():
            write = sys.stdout.write

            def prefix_output(*args, **kwargs):
                if args[0].strip():
                    write(f"{Fore.LIGHTBLUE_EX}[{self.dataplane_flow.name}]: ")
                write(*args, **kwargs)

            sys.stdout.write = prefix_output
            yield
            sys.stdout.write = write

        init(autoreset=True)
        chat_history = []
        input_name = next(
            filter(lambda key: self.dataplane_flow.inputs[key].is_chat_input, self.dataplane_flow.inputs.keys())
        )
        output_name = next(
            filter(
                lambda key: self.dataplane_flow.outputs[key].is_chat_output,
                self.dataplane_flow.outputs.keys(),
            )
        )

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
            inputs[CHAT_HISTORY] = chat_history
            chat_inputs, _ = self._resolve_data(inputs=inputs)

            with add_prefix():
                flow_result = self.flow_test(
                    inputs=chat_inputs,
                    environment_variables=environment_variables,
                    stream=False,
                )
                self._dump_result(flow_folder=self._origin_flow.code, flow_result=flow_result, prefix="chat")
                self._raise_error_when_test_failed(flow_result, show_trace=True)
            if show_step_output:
                for node_name, node_result in flow_result.node_run_infos.items():
                    print(f"{Fore.CYAN}{node_name}: ", end="")
                    try:
                        print(f"{Fore.LIGHTWHITE_EX}{json.dumps(node_result.output, indent=4)}")
                    except Exception:  # pylint: disable=broad-except
                        print(f"{Fore.LIGHTWHITE_EX}{node_result.output}")

            print(f"{Fore.YELLOW}Bot: ", end="")
            output = flow_result.output[output_name]
            print(output)
            history = {"inputs": {input_name: input_value}, "outputs": {output_name: output}}
            chat_history.append(history)

    @staticmethod
    def _dump_result(flow_folder, prefix, flow_result=None, node_result=None):

        if flow_result:
            flow_serialize_result = {
                "flow_runs": [serialize(flow_result.run_info)],
                "node_runs": [serialize(run) for run in flow_result.node_run_infos.values()],
            }
        else:
            flow_serialize_result = {
                "flow_runs": [],
                "node_runs": [serialize(node_result)],
            }
        dump_folder = Path(flow_folder) / ".promptflow"
        dump_folder.mkdir(parents=True, exist_ok=True)

        with open(dump_folder / f"{prefix}.detail.json", "w") as f:
            json.dump(flow_serialize_result, f, indent=2)
        if node_result:
            metrics = flow_serialize_result["node_runs"][0]["metrics"]
            output = flow_serialize_result["node_runs"][0]["output"]
        else:
            metrics = flow_serialize_result["flow_runs"][0]["metrics"]
            output = flow_serialize_result["flow_runs"][0]["output"]
        if metrics:
            with open(dump_folder / f"{prefix}.metrics.json", "w") as f:
                json.dump(metrics, f, indent=2)
        if output:
            with open(dump_folder / f"{prefix}.output.json", "w") as f:
                json.dump(output, f, indent=2)

    @staticmethod
    def _raise_error_when_test_failed(test_result, show_trace=False):
        from promptflow.executor.flow_executor import LineResult

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
            raise UserErrorException(f"{error_type} is raised in user code: {error_message}")
