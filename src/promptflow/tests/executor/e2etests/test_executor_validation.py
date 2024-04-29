import json
from pathlib import Path
from tempfile import mkdtemp

import pytest

from promptflow._core._errors import FlowOutputUnserializable, InvalidSource
from promptflow._core.tools_manager import APINotFound
from promptflow._utils.flow_utils import resolve_flow_path
from promptflow._utils.utils import dump_list_to_jsonl
from promptflow.batch import BatchEngine
from promptflow.contracts._errors import FailedToImportModule
from promptflow.executor import FlowExecutor
from promptflow.executor._errors import (
    DuplicateNodeName,
    EmptyOutputReference,
    GetConnectionError,
    InputNotFound,
    InputReferenceNotFound,
    InputTypeError,
    InvalidConnectionType,
    NodeCircularDependency,
    NodeInputValidationError,
    NodeReferenceNotFound,
    OutputReferenceNotFound,
    ResolveToolError,
    SingleNodeValidationError,
)

from ..utils import FLOW_ROOT, WRONG_FLOW_ROOT, get_flow_folder, get_flow_inputs_file, get_yaml_file


@pytest.mark.usefixtures("use_secrets_config_file", "dev_connections")
@pytest.mark.e2etest
class TestValidation:
    @pytest.mark.parametrize(
        "flow_folder, yml_file, error_class, inner_class, error_msg",
        [
            (
                "flow_llm_with_wrong_conn",
                "flow.dag.yaml",
                ResolveToolError,
                InvalidConnectionType,
                (
                    "Tool load failed in 'wrong_llm': "
                    "(InvalidConnectionType) Connection type CustomConnection is not supported for LLM."
                ),
            ),
            (
                "nodes_names_duplicated",
                "flow.dag.yaml",
                DuplicateNodeName,
                None,
                (
                    "Invalid node definitions found in the flow graph. Node with name 'stringify_num' appears more "
                    "than once in the node definitions in your flow, which is not allowed. To "
                    "address this issue, please review your flow and either rename or remove "
                    "nodes with identical names."
                ),
            ),
            (
                "source_file_missing",
                "flow.dag.jinja.yaml",
                ResolveToolError,
                InvalidSource,
                (
                    "Tool load failed in 'summarize_text_content': (InvalidSource) "
                    "Node source path 'summarize_text_content__variant_1.jinja2' is invalid on node "
                    "'summarize_text_content'."
                ),
            ),
            (
                "node_reference_not_found",
                "flow.dag.yaml",
                NodeReferenceNotFound,
                None,
                (
                    "Invalid node definitions found in the flow graph. Node 'divide_num_2' references a non-existent "
                    "node 'divide_num_3' in your flow. Please review your flow to ensure that the "
                    "node name is accurately specified."
                ),
            ),
            (
                "node_circular_dependency",
                "flow.dag.yaml",
                NodeCircularDependency,
                None,
                (
                    "Invalid node definitions found in the flow graph. Node circular dependency has been detected "
                    "among the nodes in your flow. Kindly review the reference relationships for "
                    "the nodes ['divide_num', 'divide_num_1', 'divide_num_2'] and resolve the "
                    "circular reference issue in the flow."
                ),
            ),
            (
                "flow_input_reference_invalid",
                "flow.dag.yaml",
                InputReferenceNotFound,
                None,
                (
                    "Invalid node definitions found in the flow graph. Node 'divide_num' references flow input 'num_1' "
                    "which is not defined in your flow. To resolve this issue, please review your "
                    "flow, ensuring that you either add the missing flow inputs or adjust node "
                    "reference to the correct flow input."
                ),
            ),
            (
                "flow_output_reference_invalid",
                "flow.dag.yaml",
                EmptyOutputReference,
                None,
                (
                    "The output 'content' for flow is incorrect. The reference is not specified for the output "
                    "'content' in the flow. To rectify this, ensure that you accurately specify "
                    "the reference in the flow."
                ),
            ),
            (
                "outputs_reference_not_valid",
                "flow.dag.yaml",
                OutputReferenceNotFound,
                None,
                (
                    "The output 'content' for flow is incorrect. The output 'content' references non-existent "
                    "node 'another_stringify_num' in your flow. To resolve this issue, please "
                    "carefully review your flow and correct the reference definition for the "
                    "output in question."
                ),
            ),
            (
                "outputs_with_invalid_flow_inputs_ref",
                "flow.dag.yaml",
                OutputReferenceNotFound,
                None,
                (
                    "The output 'num' for flow is incorrect. The output 'num' references non-existent flow "
                    "input 'num11' in your flow. Please carefully review your flow and correct "
                    "the reference definition for the output in question."
                ),
            ),
        ],
    )
    def test_executor_create_failure_type_and_message(
        self, flow_folder, yml_file, error_class, inner_class, error_msg, dev_connections
    ):
        with pytest.raises(error_class) as exc_info:
            FlowExecutor.create(get_yaml_file(flow_folder, WRONG_FLOW_ROOT, yml_file), dev_connections)
        if isinstance(exc_info.value, ResolveToolError):
            assert isinstance(exc_info.value.inner_exception, inner_class)
        assert error_msg == exc_info.value.message

    @pytest.mark.parametrize(
        "flow_folder, yml_file, error_class, inner_class",
        [
            ("source_file_missing", "flow.dag.python.yaml", ResolveToolError, InvalidSource),
        ],
    )
    def test_executor_create_failure_type(self, flow_folder, yml_file, error_class, inner_class, dev_connections):
        with pytest.raises(error_class) as e:
            FlowExecutor.create(get_yaml_file(flow_folder, WRONG_FLOW_ROOT, yml_file), dev_connections)
        if isinstance(e.value, ResolveToolError):
            assert isinstance(e.value.inner_exception, inner_class)

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
        "flow_folder, error_class, inner_class",
        [
            ("invalid_connection", ResolveToolError, GetConnectionError),
            ("tool_type_missing", ResolveToolError, NotImplementedError),
            ("wrong_module", FailedToImportModule, None),
            ("wrong_api", ResolveToolError, APINotFound),
        ],
    )
    def test_invalid_flow_dag(self, flow_folder, error_class, inner_class, dev_connections):
        with pytest.raises(error_class) as e:
            FlowExecutor.create(get_yaml_file(flow_folder, WRONG_FLOW_ROOT), dev_connections)
        if isinstance(e.value, ResolveToolError):
            assert isinstance(e.value.inner_exception, inner_class)

    @pytest.mark.parametrize(
        "flow_folder, line_input, error_class",
        [
            ("simple_flow_with_python_tool", {"num11": "22"}, InputNotFound),
            ("simple_flow_with_python_tool", {"num": "hello"}, InputTypeError),
            ("python_tool_with_simple_image_without_default", {}, InputNotFound),
        ],
    )
    def test_flow_run_input_type_invalid(self, flow_folder, line_input, error_class, dev_connections):
        # Flow run -  the input is from get_partial_line_inputs()
        executor = FlowExecutor.create(get_yaml_file(flow_folder, FLOW_ROOT), dev_connections)
        with pytest.raises(error_class):
            executor.exec_line(line_input)

    def test_invalid_flow_run_inputs_should_not_saved_to_run_info(self, dev_connections):
        flow_folder = "simple_flow_with_python_tool"
        executor = FlowExecutor.create(get_yaml_file(flow_folder, FLOW_ROOT), dev_connections, raise_ex=False)
        invalid_input = {"num": "hello"}
        result = executor.exec_line(invalid_input)
        # For invalid inputs, we don't assigin them to run info.
        assert result.run_info.inputs is None

    def test_valid_flow_run_inpust_should_saved_to_run_info(self, dev_connections):
        flow_folder = "simple_flow_with_python_tool"
        executor = FlowExecutor.create(get_yaml_file(flow_folder, FLOW_ROOT), dev_connections, raise_ex=False)
        valid_input = {"num": 22}
        result = executor.exec_line(valid_input)
        # For valid inputs, we assigin them to run info.
        assert result.run_info.inputs == valid_input

    @pytest.mark.parametrize(
        "flow_folder, line_input, error_class, error_msg",
        [
            (
                "flow_output_unserializable",
                {"num": "22"},
                FlowOutputUnserializable,
                (
                    "The output 'content' for flow is incorrect. The output value is not JSON serializable. "
                    "JSON dump failed: (TypeError) Object of type UnserializableClass is not JSON serializable. "
                    "Please verify your flow output and make sure the value serializable."
                ),
            ),
        ],
    )
    def test_flow_run_execution_errors(self, flow_folder, line_input, error_class, error_msg, dev_connections):
        executor = FlowExecutor.create(get_yaml_file(flow_folder, WRONG_FLOW_ROOT), dev_connections)
        # For now, there exception is designed to be swallowed in executor. But Run Info would have the error details
        res = executor.exec_line(line_input)
        assert error_msg == res.run_info.error["message"]

    @pytest.mark.parametrize(
        "flow_folder, inputs_mapping, error_message, error_class",
        [
            (
                "simple_flow_with_python_tool",
                {"num": "${data.num}"},
                (
                    "The input for flow is incorrect. The value for flow input 'num' in line 0 of input data does not "
                    "match the expected type 'int'. Please change flow input type or adjust the input value in "
                    "your input data."
                ),
                "InputTypeError",
            ),
        ],
    )
    def test_batch_run_input_type_invalid(
        self, flow_folder, inputs_mapping, error_message, error_class, dev_connections
    ):
        # Bulk run - the input is from sample.json
        batch_engine = BatchEngine(
            get_yaml_file(flow_folder), get_flow_folder(flow_folder), connections=dev_connections
        )
        input_dirs = {"data": get_flow_inputs_file(flow_folder)}
        output_dir = Path(mkdtemp())
        batch_results = batch_engine.run(input_dirs, inputs_mapping, output_dir)

        assert error_message in str(
            batch_results.error_summary.error_list[0].error
        ), f"Expected message {error_message} but got {str(batch_results.error_summary.error_list[0].error)}"

        assert error_class in str(
            batch_results.error_summary.error_list[0].error
        ), f"Expected message {error_class} but got {str(batch_results.error_summary.error_list[0].error)}"

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
            (
                FLOW_ROOT,
                "simple_flow_with_python_tool",
                "bad_node_name",
                {"num": "22"},
                SingleNodeValidationError,
                (
                    "Validation failed when attempting to execute the node. Node 'bad_node_name' is not found in flow "
                    "'flow.dag.yaml'. Please change node name or correct the flow file."
                ),
            ),
            (
                WRONG_FLOW_ROOT,
                "node_missing_type_or_source",
                "divide_num",
                {"num": "22"},
                SingleNodeValidationError,
                (
                    "Validation failed when attempting to execute the node. Properties 'source' or 'type' are not "
                    "specified for Node 'divide_num' in flow 'flow.dag.yaml'. Please make sure "
                    "these properties are in place and try again."
                ),
            ),
        ],
    )
    def test_single_node_input_type_invalid(
        self, path_root: str, flow_folder, node_name, line_input, error_class, error_msg, dev_connections
    ):
        # Single Node run - the inputs are from flow_inputs + dependency_nodes_outputs
        _, flow_file = resolve_flow_path(flow_folder, path_root, check_flow_exist=False)
        with pytest.raises(error_class) as exe_info:
            FlowExecutor.load_and_exec_node(
                flow_file=flow_file,
                node_name=node_name,
                flow_inputs=line_input,
                dependency_nodes_outputs={},
                connections=dev_connections,
                working_dir=Path(path_root) / flow_folder,
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
        with pytest.raises(ResolveToolError, match=msg) as e:
            FlowExecutor.create(get_yaml_file(flow_folder, FLOW_ROOT), dev_connections)
        assert isinstance(e.value.inner_exception, NodeInputValidationError)

    @pytest.mark.parametrize(
        "flow_folder, batch_input, raise_on_line_failure, error_class",
        [
            ("simple_flow_with_python_tool", [{"num": "hello"}], True, Exception),
            ("simple_flow_with_python_tool", [{"num": "hello"}], False, InputTypeError),
            ("simple_flow_with_python_tool", [{"num": "22"}], True, None),
            ("simple_flow_with_python_tool", [{"num": "22"}], False, None),
        ],
    )
    def test_batch_run_raise_on_line_failure(
        self, flow_folder, batch_input, raise_on_line_failure, error_class, dev_connections
    ):
        # Bulk run - the input is from sample.json
        batch_engine = BatchEngine(
            get_yaml_file(flow_folder), get_flow_folder(flow_folder), connections=dev_connections
        )
        # prepare input file and output dir
        input_file = Path(mkdtemp()) / "inputs.jsonl"
        dump_list_to_jsonl(input_file, batch_input)
        input_dirs = {"data": input_file}
        output_dir = Path(mkdtemp())
        inputs_mapping = {"num": "${data.num}"}

        if error_class is None:
            batch_result = batch_engine.run(
                input_dirs, inputs_mapping, output_dir, raise_on_line_failure=raise_on_line_failure
            )
            assert batch_result.total_lines == 1
            assert batch_result.completed_lines == 1
            assert batch_result.error_summary.error_list == []
        else:
            if raise_on_line_failure:
                with pytest.raises(error_class):
                    batch_engine.run(
                        input_dirs, inputs_mapping, output_dir, raise_on_line_failure=raise_on_line_failure
                    )
            else:
                batch_result = batch_engine.run(
                    input_dirs, inputs_mapping, output_dir, raise_on_line_failure=raise_on_line_failure
                )
                assert batch_result.total_lines == 1
                assert batch_result.failed_lines == 1
                assert error_class.__name__ in json.dumps(batch_result.error_summary.error_list[0].error)
