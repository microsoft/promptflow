# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
# this file is a middle layer between the local SDK and executor.
import contextlib
import json
import logging
import sys
import time
from pathlib import Path
from types import GeneratorType
from typing import Any, Iterable, Mapping

from promptflow._sdk._constants import CHAT_HISTORY, LOGGER_NAME, PROMPT_FLOW_DIR_NAME
from promptflow._sdk._utils import parse_variant
from promptflow._sdk.entities._flow import Flow
from promptflow._sdk.operations._local_storage_operations import LoggerOperations
from promptflow._sdk.operations._run_submitter import SubmitterHelper, variant_overwrite_context
from promptflow._utils.context_utils import _change_working_dir
from promptflow._utils.dataclass_serializer import serialize
from promptflow._utils.exception_utils import ErrorResponse
from promptflow.contracts.flow import Flow as ExecutableFlow
from promptflow.contracts.run_info import Status
from promptflow.exceptions import UserErrorException

logger = logging.getLogger(LOGGER_NAME)


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

    def _resolve_data(self, node_name: str = None, inputs: dict = None):
        """
        Resolve input to flow/node test inputs.
        Raise user error when missing required inputs. And log warning when unknown inputs appeared.

        :param node_name: Node name.
        :type node_name: str
        :param inputs: Inputs of flow/node test.
        :type inputs: dict
        :return: Dict of flow inputs, Dict of reference node output.
        :rtype: dict, dict
        """
        from promptflow.contracts.flow import InputValueType

        inputs = (inputs or {}).copy()
        flow_inputs, dependency_nodes_outputs, merged_inputs = {}, {}, {}
        missing_inputs = []
        # Using default value of inputs as flow input
        if node_name:
            node = next(filter(lambda item: item.name == node_name, self.dataplane_flow.nodes), None)
            if not node:
                raise UserErrorException(f"Cannot find {node_name} in the flow.")
            for name, value in node.inputs.items():
                if value.value_type == InputValueType.NODE_REFERENCE:
                    input_name = f"{value.value}.{value.section}"
                    if input_name in inputs:
                        dependency_input = inputs.pop(input_name)
                    elif name in inputs:
                        dependency_input = inputs.pop(name)
                    else:
                        missing_inputs.append(name)
                        continue
                    dependency_nodes_outputs[value.value] = dependency_input
                    merged_inputs[name] = dependency_input
                elif value.value_type == InputValueType.FLOW_INPUT:
                    input_name = f"{value.prefix}{value.value}"
                    if input_name in inputs:
                        flow_input = inputs.pop(input_name)
                    elif name in inputs:
                        flow_input = inputs.pop(name)
                    else:
                        flow_input = self.dataplane_flow.inputs[value.value].default
                        if flow_input is None:
                            missing_inputs.append(name)
                            continue
                    flow_inputs[value.value] = flow_input
                    merged_inputs[name] = flow_input
                else:
                    flow_inputs[name] = inputs.pop(name) if name in inputs else value.value
                    merged_inputs[name] = flow_inputs[name]
        else:
            for name, value in self.dataplane_flow.inputs.items():
                if name in inputs:
                    flow_inputs[name] = inputs.pop(name)
                    merged_inputs[name] = flow_inputs[name]
                else:
                    if value.default is None:
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

    def flow_test(self, inputs: Mapping[str, Any], environment_variables: dict = None, stream: bool = True):
        from promptflow.executor.flow_executor import LINE_NUMBER_KEY, FlowExecutor

        connections = SubmitterHelper.resolve_connections(flow=self.flow)
        # resolve environment variables
        SubmitterHelper.resolve_environment_variables(environment_variables=environment_variables)
        environment_variables = environment_variables if environment_variables else {}
        SubmitterHelper.init_env(environment_variables=environment_variables)

        with LoggerOperations(log_path=self.flow.code / PROMPT_FLOW_DIR_NAME / "flow.log").setup_logger(stream=stream):
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

    def interactive_test(self, inputs: Mapping[str, Any], environment_variables: dict = None):
        from promptflow.executor.flow_executor import FlowExecutor

        connections = SubmitterHelper.resolve_connections(flow=self.flow)
        # resolve environment variables
        SubmitterHelper.resolve_environment_variables(environment_variables=environment_variables)
        environment_variables = environment_variables if environment_variables else {}
        SubmitterHelper.init_env(environment_variables=environment_variables)

        with LoggerOperations(log_path=self.flow.code / PROMPT_FLOW_DIR_NAME / "flow.log").setup_logger(stream=False):
            flow_executor = FlowExecutor.create(self.flow.path, connections, self.flow.code, raise_ex=False)
            # TODO modify to call the method in the flow server
            flow_executor._run_tracker.allow_generator_types = True
            flow_executor.enable_streaming_for_llm_flow(lambda: True)
            line_result = flow_executor._exec(inputs)
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

        with LoggerOperations(log_path=self.flow.code / PROMPT_FLOW_DIR_NAME / f"{node_name}.node.log").setup_logger(
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
            3. Prefix the output for distinction.
        """
        from colorama import Fore, init

        @contextlib.contextmanager
        def change_logger_level(level):
            origin_level = logger.level
            logger.setLevel(level)
            yield
            logger.setLevel(origin_level)

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

        def print_chat_output(output):
            chat_output = output
            if isinstance(output, Iterable):
                chat_output = ""
                for event in output:
                    print(event, end="")
                    # For better animation effects
                    time.sleep(0.01)
                    chat_output += event
                # Print a new line at the end of the response
                print()
            else:
                print(chat_output)
            return chat_output

        def get_generator_values(generator):
            if isinstance(generator, GeneratorType):
                if generator not in generator_record:
                    generator_record[generator] = list(generator)
                return generator_record[generator]
            else:
                return generator

        def resolve_generator(flow_result, flow_outputs, node_outputs):
            flow_outputs = flow_outputs or {}
            node_outputs = node_outputs or {}
            # resolve generator in flow result
            for k, v in flow_result.run_info.output.items():
                if isinstance(v, GeneratorType):
                    flow_output = flow_outputs.get(k, "".join(v))
                    flow_result.run_info.output[k] = flow_output
                    flow_result.run_info.result[k] = flow_output
                    flow_result.output[k] = flow_output

            # resolve generator in node outputs
            for node_name, node in flow_result.node_run_infos.items():
                if isinstance(node.output, GeneratorType):
                    node_output = node_outputs.get(node_name, "".join(node.output))
                    node.output = node_output
                    node.result = node_output

            return flow_result

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
            with change_logger_level(level=logging.WARNING):
                chat_inputs, _ = self._resolve_data(inputs=inputs)

            with add_prefix():
                flow_result = self.interactive_test(
                    inputs=chat_inputs,
                    environment_variables=environment_variables,
                )
                self._raise_error_when_test_failed(flow_result, show_trace=True)
            node_outputs = {}
            if show_step_output:
                for node_name, node_result in flow_result.node_run_infos.items():
                    print(f"{Fore.CYAN}{node_name}: ", end="")
                    try:
                        # TODO executor return a type string of generator
                        node_output = node_result.output
                        if isinstance(node_result.output, GeneratorType):
                            node_output = "".join(get_generator_values(node_result.output))
                        print(f"{Fore.LIGHTWHITE_EX}{json.dumps(node_output, indent=4)}")
                    except Exception:  # pylint: disable=broad-except
                        print(f"{Fore.LIGHTWHITE_EX}{node_output}")
                    node_outputs[node_name] = node_output

            print(f"{Fore.YELLOW}Bot: ", end="")
            chat_output = get_generator_values(flow_result.output[output_name])
            chat_output = print_chat_output(chat_output)
            flow_outputs = {k: v for k, v in flow_result.output.items()}
            flow_outputs[output_name] = chat_output
            history = {"inputs": {input_name: input_value}, "outputs": flow_outputs}
            chat_history.append(history)
            flow_result = resolve_generator(flow_result, flow_outputs, node_outputs)
            self._dump_result(flow_folder=self._origin_flow.code, flow_result=flow_result, prefix="chat")

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
        dump_folder = Path(flow_folder) / PROMPT_FLOW_DIR_NAME
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
            raise UserErrorException(f"{error_type}: {error_message}")
