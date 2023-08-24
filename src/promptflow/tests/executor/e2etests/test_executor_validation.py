import json

import pytest

from promptflow._core.tool_meta_generator import PythonParsingError
from promptflow._core.tools_manager import APINotFound
from promptflow.contracts._errors import FailedToImportModule
from promptflow.contracts.run_info import Status
from promptflow.executor import FlowExecutor
from promptflow.executor._errors import (
    ConnectionNotFound,
    DuplicateNodeName,
    EmptyOutputError,
    InputNotFound,
    InputReferenceNotFound,
    InputTypeError,
    InvalidFlowRequest,
    InvalidSource,
    NodeCircularDependency,
    NodeInputValidationError,
    NodeReferenceNotFound,
    OutputReferenceNotFound,
)
from promptflow.executor.flow_executor import BulkResult

from ..utils import FLOW_ROOT, WRONG_FLOW_ROOT, get_yaml_file


@pytest.mark.usefixtures("use_secrets_config_file", "dev_connections")
@pytest.mark.e2etest
class TestValidation:
    @pytest.mark.parametrize(
        "flow_folder, yml_file, error_class",
        [
            ("nodes_names_duplicated", "flow.dag.yaml", DuplicateNodeName),
            ("source_file_missing", "flow.dag.python.yaml", PythonParsingError),
            ("source_file_missing", "flow.dag.jinja.yaml", InvalidSource),
            ("node_reference_not_found", "flow.dag.yaml", NodeReferenceNotFound),
            ("node_circular_dependency", "flow.dag.yaml", NodeCircularDependency),
            ("flow_input_reference_invalid", "flow.dag.yaml", InputReferenceNotFound),
            ("flow_output_reference_invalid", "flow.dag.yaml", EmptyOutputError),
        ],
    )
    def test_executor_create(self, flow_folder, yml_file, error_class, dev_connections):
        with pytest.raises(error_class):
            FlowExecutor.create(get_yaml_file(flow_folder, WRONG_FLOW_ROOT, yml_file), dev_connections)

    @pytest.mark.parametrize(
        "ordered_flow_folder,  unordered_flow_folder",
        [
            ("web_classification_no_variants", "web_classification_no_variants_unordered"),
        ],
    )
    def test_node_topology_in_order(self, ordered_flow_folder, unordered_flow_folder, dev_connections):
        ordered_executor = FlowExecutor.create(get_yaml_file(ordered_flow_folder), dev_connections)
        unordered_executor = FlowExecutor.create(get_yaml_file(unordered_flow_folder), dev_connections)

        for node1, node2 in zip(ordered_executor._flow.nodes, unordered_executor._flow.nodes):
            assert node1.name == node2.name

    @pytest.mark.parametrize(
        "flow_folder, error_class",
        [
            ("outputs_reference_not_valid", OutputReferenceNotFound),
            ("outputs_with_invalid_flow_inputs_ref", OutputReferenceNotFound),
            ("invalid_connection", ConnectionNotFound),
            ("tool_type_missing", NotImplementedError),
            ("wrong_module", FailedToImportModule),
            ("wrong_api", APINotFound),
            ("wrong_provider", APINotFound),
        ],
    )
    def test_invalid_flow_dag(self, flow_folder, error_class, dev_connections):
        with pytest.raises(error_class):
            FlowExecutor.create(get_yaml_file(flow_folder, WRONG_FLOW_ROOT), dev_connections)

    @pytest.mark.parametrize(
        "flow_folder, line_input, error_class",
        [
            ("simple_flow_with_python_tool", {"num11": "22"}, InputNotFound),
            ("simple_flow_with_python_tool", {"num": "hello"}, InputTypeError),
        ],
    )
    def test_flow_run_input_type_invalid(self, flow_folder, line_input, error_class, dev_connections):
        # Flow run -  the input is from get_partial_line_inputs()
        executor = FlowExecutor.create(get_yaml_file(flow_folder, FLOW_ROOT), dev_connections)
        with pytest.raises(error_class):
            executor.exec_line(line_input)

    @pytest.mark.parametrize(
        "flow_folder, batch_input, error_message, error_class",
        [
            (
                "simple_flow_with_python_tool",
                [{"num11": "22"}],
                "Input 'num' in line 0 is not provided for flow.",
                "InputNotFound",
            ),
            (
                "simple_flow_with_python_tool",
                [{"num": "hello"}],
                "Input 'num' in line 0 for flow 'default_flow' of value hello is not type int.",
                "InputTypeError",
            ),
        ],
    )
    def test_bulk_run_input_type_invalid(self, flow_folder, batch_input, error_message, error_class, dev_connections):
        # Bulk run - the input is from sample.json
        executor = FlowExecutor.create(get_yaml_file(flow_folder, FLOW_ROOT), dev_connections)
        bulk_result = executor.exec_bulk(
            batch_input,
        )
        assert error_message in str(
            bulk_result.line_results[0].run_info.error
        ), f"Expected message {error_message} but got {str(bulk_result.line_results[0].run_info.error)}"
        assert error_class in str(
            bulk_result.line_results[0].run_info.error
        ), f"Expected message {error_class} but got {str(bulk_result.line_results[0].run_info.error)}"

    @pytest.mark.parametrize(
        "path_root, flow_folder, node_name, line_input, error_class",
        [
            (FLOW_ROOT, "simple_flow_with_python_tool", "divide_num", {"num11": "22"}, InputNotFound),
            (FLOW_ROOT, "simple_flow_with_python_tool", "divide_num", {"num": "hello"}, InputTypeError),
            (WRONG_FLOW_ROOT, "flow_input_reference_invalid", "divide_num", {"num": "22"}, InputNotFound),
        ],
    )
    def test_single_node_input_type_invalid(
        self, path_root: str, flow_folder, node_name, line_input, error_class, dev_connections
    ):
        # Single Node run - the inputs are from flow_inputs + dependency_nodes_outputs
        with pytest.raises(error_class):
            FlowExecutor.load_and_exec_node(
                flow_file=get_yaml_file(flow_folder, path_root),
                node_name=node_name,
                flow_inputs=line_input,
                dependency_nodes_outputs={},
                connections=dev_connections,
                raise_ex=True,
            )

    @pytest.mark.parametrize(
        "flow_folder, msg",
        [
            (
                "prompt_tool_with_duplicated_inputs",
                "Invalid inputs {'template'} in prompt template of node prompt_tool_with_duplicated_inputs. "
                "These inputs are duplicated with the reserved parameters of prompt tool.",
            ),
            (
                "llm_tool_with_duplicated_inputs",
                "Invalid inputs {'prompt'} in prompt template of node llm_tool_with_duplicated_inputs. "
                "These inputs are duplicated with the parameters of AzureOpenAI.completion.",
            ),
        ],
    )
    def test_flow_run_with_duplicated_inputs(self, flow_folder, msg, dev_connections):
        with pytest.raises(NodeInputValidationError, match=msg):
            FlowExecutor.create(get_yaml_file(flow_folder, FLOW_ROOT), dev_connections)

    @pytest.mark.parametrize(
        "flow_folder, batch_input, raise_on_line_failure, error_class",
        [
            ("simple_flow_with_python_tool", [{"num11": "22"}], True, Exception),
            ("simple_flow_with_python_tool", [{"num11": "22"}], False, InputNotFound),
            ("simple_flow_with_python_tool", [{"num": "hello"}], True, Exception),
            ("simple_flow_with_python_tool", [{"num": "hello"}], False, InputTypeError),
            ("simple_flow_with_python_tool", [{"num": "22"}], True, None),
            ("simple_flow_with_python_tool", [{"num": "22"}], False, None),
        ],
    )
    def test_bulk_run_raise_on_line_failure(
        self, flow_folder, batch_input, raise_on_line_failure, error_class, dev_connections
    ):
        executor = FlowExecutor.create(get_yaml_file(flow_folder, FLOW_ROOT), dev_connections, raise_ex=False)
        if error_class is None:
            result = executor.exec_bulk(batch_input, raise_on_line_failure=raise_on_line_failure)
            assert len(result.line_results) == 1
            assert result.line_results[0].run_info.status == Status.Completed
            assert result.line_results[0].run_info.error is None
        else:
            if raise_on_line_failure:
                with pytest.raises(error_class):
                    executor.exec_bulk(batch_input, raise_on_line_failure=raise_on_line_failure)
            else:
                result = executor.exec_bulk(batch_input, raise_on_line_failure=raise_on_line_failure)
                assert result.line_results[0].run_info.status == Status.Failed
                assert error_class.__name__ in json.dumps(result.line_results[0].run_info.error)

    @pytest.mark.parametrize(
        "flow_folder, batch_input, validate, error_class,",
        [
            ("simple_flow_with_python_tool", [{"num": "14"}], True, None),
            ("simple_flow_with_python_tool", [{"num": "14"}], False, TypeError),
            ("simple_flow_with_python_tool", [{"num": 14}], False, None),
            ("simple_flow_with_python_tool", [{"num11": "14"}], True, InputNotFound),
            ("simple_flow_with_python_tool", [{"num11": "14"}], False, InvalidFlowRequest),
            ("simple_flow_with_python_tool", [{"num": "hello"}], True, InputTypeError),
            ("simple_flow_with_python_tool", [{"num": "hello"}], False, TypeError),
        ],
    )
    def test_bulk_run_validate_inputs(self, flow_folder, batch_input, validate, error_class, dev_connections):
        executor = FlowExecutor.create(get_yaml_file(flow_folder, FLOW_ROOT), dev_connections, raise_ex=False)

        result = executor.exec_bulk(batch_input, validate_inputs=validate)
        assert isinstance(result, BulkResult)
        assert len(result.line_results) == len(batch_input)
        if error_class is None:
            assert result.line_results[0].run_info.status == Status.Completed
            assert result.line_results[0].run_info.error is None
        else:
            assert result.line_results[0].run_info.status == Status.Failed
            assert error_class.__name__ in json.dumps(result.line_results[0].run_info.error)
