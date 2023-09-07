import json
import sys

import pytest

from promptflow._core.tool_meta_generator import PythonParsingError
from promptflow._core.tools_manager import APINotFound
from promptflow.contracts._errors import FailedToImportModule
from promptflow.contracts.run_info import Status
from promptflow.executor import FlowExecutor
from promptflow.executor._errors import (
    ConnectionNotFound,
    DuplicateNodeName,
    EmptyOutputReference,
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
        "flow_folder, yml_file, error_class, error_msg",
        [
            (
                "nodes_names_duplicated",
                "flow.dag.yaml",
                DuplicateNodeName,
                (
                    "Flow is defined incorrectly. Node with name 'stringify_num' appears more "
                    "than once in the node definitions in your flow, which is not allowed. To "
                    "address this issue, please review your flow and either rename or remove "
                    "nodes with identical names."
                ),
            ),
            (
                "source_file_missing",
                "flow.dag.jinja.yaml",
                InvalidSource,
                (
                    "Node source path 'summarize_text_content__variant_1.jinja2' is invalid on "
                    "node 'summarize_text_content'."
                ),
            ),
            (
                "node_reference_not_found",
                "flow.dag.yaml",
                NodeReferenceNotFound,
                (
                    "Flow is defined incorrectly. Node 'divide_num_2' references a non-existent "
                    "node 'divide_num_3' in your flow. Please review your flow to ensure that the "
                    "node name is accurately specified."
                ),
            ),
            (
                "node_circular_dependency",
                "flow.dag.yaml",
                NodeCircularDependency,
                (
                    "Flow is defined incorrectly. Node circular dependency has been detected "
                    "among the nodes in your flow. Kindly review the reference relationships for "
                    "the nodes ['divide_num', 'divide_num_1', 'divide_num_2'] and resolve the "
                    "circular reference issue in the flow."
                ),
            ),
            (
                "flow_input_reference_invalid",
                "flow.dag.yaml",
                InputReferenceNotFound,
                (
                    "Flow is defined incorrectly. Node 'divide_num' references flow input 'num_1' "
                    "which is not defined in your flow. To resolve this issue, please review your "
                    "flow, ensuring that you either add the missing flow inputs or adjust node "
                    "reference to the correct flow input."
                ),
            ),
            (
                "flow_output_reference_invalid",
                "flow.dag.yaml",
                EmptyOutputReference,
                (
                    "Flow is defined incorrectly. The reference is not specified for the output "
                    "'content' in the flow. To rectify this, ensure that you accurately specify "
                    "the reference in the flow."
                ),
            ),
            (
                "outputs_reference_not_valid",
                "flow.dag.yaml",
                OutputReferenceNotFound,
                (
                    "Flow is defined incorrectly. The output 'content' references non-existent "
                    "node 'another_stringify_num' in your flow. To resolve this issue, please "
                    "carefully review your flow and correct the reference definition for the "
                    "output in question."
                ),
            ),
            (
                "outputs_with_invalid_flow_inputs_ref",
                "flow.dag.yaml",
                OutputReferenceNotFound,
                (
                    "Flow is defined incorrectly. The output 'num' references non-existent flow "
                    "input 'num11' in your flow. Please carefully review your flow and correct "
                    "the reference definition for the output in question."
                ),
            ),
        ],
    )
    def test_executor_create_failure_type_and_message(
        self, flow_folder, yml_file, error_class, error_msg, dev_connections
    ):
        with pytest.raises(error_class) as exc_info:
            FlowExecutor.create(get_yaml_file(flow_folder, WRONG_FLOW_ROOT, yml_file), dev_connections)
        assert error_msg == exc_info.value.message

    @pytest.mark.parametrize(
        "flow_folder, yml_file, error_class",
        [
            ("source_file_missing", "flow.dag.python.yaml", PythonParsingError),
        ],
    )
    def test_executor_create_failure_type(self, flow_folder, yml_file, error_class, dev_connections):
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
                (
                    "The value for flow input 'num' is not provided in line 0 of input data. "
                    "Please review your input data or remove this input in your flow if it's no longer needed."
                ),
                "InputNotFound",
            ),
            (
                "simple_flow_with_python_tool",
                [{"num": "hello"}],
                (
                    "The input for flow is incorrect. The value for flow input 'num' in line 0 of input data does not "
                    "match the expected type 'int'. Please change flow input type or adjust the input value in "
                    "your input data."
                ),
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
        if (
            (sys.version_info.major == 3)
            and (sys.version_info.minor >= 11)
            and ((sys.platform == "linux") or (sys.platform == "darwin"))
        ):
            # Python >= 3.11 has a different error message on linux and macos
            error_message_compare = error_message.replace("int", "ValueType.INT")
            assert error_message_compare in str(
                bulk_result.line_results[0].run_info.error
            ), f"Expected message {error_message_compare} but got {str(bulk_result.line_results[0].run_info.error)}"
        else:
            assert error_message in str(
                bulk_result.line_results[0].run_info.error
            ), f"Expected message {error_message} but got {str(bulk_result.line_results[0].run_info.error)}"
        assert error_class in str(
            bulk_result.line_results[0].run_info.error
        ), f"Expected message {error_class} but got {str(bulk_result.line_results[0].run_info.error)}"

    @pytest.mark.parametrize(
        "path_root, flow_folder, node_name, line_input, error_class, error_msg",
        [
            (
                FLOW_ROOT,
                "simple_flow_with_python_tool",
                "divide_num",
                {"num11": "22"},
                InputNotFound,
                (
                    "The input for node is incorrect. Node input 'num' is not found in input data "
                    "for node 'divide_num'. Please verify the inputs data for the node."
                ),
            ),
            (
                FLOW_ROOT,
                "simple_flow_with_python_tool",
                "divide_num",
                {"num": "hello"},
                InputTypeError,
                (
                    "The input for node is incorrect. Value for input 'num' of node 'divide_num' "
                    "is not type 'int'. Please review and rectify the input data."
                ),
            ),
            (
                WRONG_FLOW_ROOT,
                "flow_input_reference_invalid",
                "divide_num",
                {"num": "22"},
                InputNotFound,
                (
                    "The input for node is incorrect. Node input 'num_1' is not found from flow "
                    "inputs of node 'divide_num'. Please review the node definition in your flow."
                ),
            ),
        ],
    )
    def test_single_node_input_type_invalid(
        self, path_root: str, flow_folder, node_name, line_input, error_class, error_msg, dev_connections
    ):
        # Single Node run - the inputs are from flow_inputs + dependency_nodes_outputs
        with pytest.raises(error_class) as exe_info:
            FlowExecutor.load_and_exec_node(
                flow_file=get_yaml_file(flow_folder, path_root),
                node_name=node_name,
                flow_inputs=line_input,
                dependency_nodes_outputs={},
                connections=dev_connections,
                raise_ex=True,
            )

        assert error_msg == exe_info.value.message

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
