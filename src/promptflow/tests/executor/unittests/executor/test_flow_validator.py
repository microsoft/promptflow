import sys

import pytest
import yaml

from promptflow.contracts.flow import Flow
from promptflow.executor._errors import InputParseError, InvalidAggregationInput, InvalidFlowRequest
from promptflow.executor.flow_validator import FlowValidator

from ...utils import WRONG_FLOW_ROOT, get_yaml_file


@pytest.mark.unittest
class TestFlowValidator:
    @pytest.mark.parametrize(
        "flow_folder, expected_node_order",
        [
            ("unordered_nodes", ["first_node", "second_node", "third_node"]),
            ("unordered_nodes_with_skip", ["first_node", "second_node", "third_node"]),
            ("unordered_nodes_with_activate", ["first_node", "second_node", "third_node"]),
        ],
    )
    def test_ensure_nodes_order(self, flow_folder, expected_node_order):
        flow_yaml = get_yaml_file(flow_folder)
        with open(flow_yaml, "r") as fin:
            flow = Flow.deserialize(yaml.safe_load(fin))
        flow = FlowValidator._ensure_nodes_order(flow)
        node_order = [node.name for node in flow.nodes]
        assert node_order == expected_node_order

    @pytest.mark.parametrize(
        "flow_folder, error_message",
        [
            (
                "nodes_cycle",
                (
                    "Invalid node definitions found in the flow graph. Node circular dependency has been detected "
                    "among the nodes in your flow. Kindly review the reference relationships for the nodes "
                    "['first_node', 'second_node'] and resolve the circular reference issue in the flow."
                ),
            ),
            (
                "nodes_cycle_with_skip",
                (
                    "Invalid node definitions found in the flow graph. Node circular dependency has been detected "
                    "among the nodes in your flow. Kindly review the reference relationships for the nodes "
                    "['first_node', 'second_node'] and resolve the circular reference issue in the flow."
                ),
            ),
            (
                "nodes_cycle_with_activate",
                (
                    "Invalid node definitions found in the flow graph. Node circular dependency has been detected "
                    "among the nodes in your flow. Kindly review the reference relationships "
                    "for the nodes ['first_node', 'second_node'] and resolve the circular reference issue in the flow."
                ),
            ),
            (
                "wrong_node_reference",
                (
                    "Invalid node definitions found in the flow graph. Node 'second_node' references a non-existent "
                    "node 'third_node' in your flow. Please review your flow to ensure that the node "
                    "name is accurately specified."
                ),
            ),
            (
                "non_aggregation_reference_aggregation",
                (
                    "Invalid node definitions found in the flow graph. Non-aggregate node 'test_node' "
                    "cannot reference aggregate nodes {'calculate_accuracy'}. Please review and rectify "
                    "the node reference."
                ),
            ),
            (
                "aggregation_skip_reference_non_aggregation",
                (
                    "Invalid node definitions found in the flow graph. Non-aggregation nodes cannot be "
                    "referenced in the skip config of the aggregation node 'calculate_accuracy'. Please "
                    "review and rectify the node reference."
                ),
            ),
            (
                "aggregation_activate_reference_non_aggregation",
                (
                    "Invalid node definitions found in the flow graph. Non-aggregation node 'grade' cannot be "
                    "referenced in the activate config of the aggregation node 'calculate_accuracy'. Please "
                    "review and rectify the node reference."
                ),
            ),
        ],
    )
    def test_ensure_nodes_order_with_exception(self, flow_folder, error_message):
        flow_yaml = get_yaml_file(flow_folder, root=WRONG_FLOW_ROOT)
        with open(flow_yaml, "r") as fin:
            flow = Flow.deserialize(yaml.safe_load(fin))
        with pytest.raises(InvalidFlowRequest) as e:
            FlowValidator._ensure_nodes_order(flow)
        assert str(e.value) == error_message, "Expected: {}, Actual: {}".format(error_message, str(e.value))

    @pytest.mark.parametrize(
        "aggregated_flow_inputs, aggregation_inputs, error_message",
        [
            (
                {},
                {
                    "input1": "value1",
                },
                "The input for aggregation is incorrect. "
                "The value for aggregated reference input 'input1' should be a list, "
                "but received str. Please adjust the input value to match the expected format.",
            ),
            (
                {
                    "input1": "value1",
                },
                {},
                "The input for aggregation is incorrect. "
                "The value for aggregated flow input 'input1' should be a list, "
                "but received str. Please adjust the input value to match the expected format.",
            ),
            (
                {"input1": ["value1_1", "value1_2"]},
                {"input_2": ["value2_1"]},
                "The input for aggregation is incorrect. The length of all aggregated inputs should be the same. "
                "Current input lengths are: {'input1': 2, 'input_2': 1}. "
                "Please adjust the input value in your input data.",
            ),
            (
                {
                    "input1": "value1",
                },
                {
                    "input1": "value1",
                },
                "The input for aggregation is incorrect. "
                "The input 'input1' appears in both aggregated flow input and aggregated reference input. "
                "Please remove one of them and try the operation again.",
            ),
        ],
    )
    def test_validate_aggregation_inputs_error(self, aggregated_flow_inputs, aggregation_inputs, error_message):
        with pytest.raises(InvalidAggregationInput) as e:
            FlowValidator._validate_aggregation_inputs(aggregated_flow_inputs, aggregation_inputs)
        assert str(e.value) == error_message

    @pytest.mark.parametrize(
        "flow_folder",
        ["simple_flow_with_python_tool_and_aggregate"],
    )
    def test_ensure_outputs_valid_with_aggregation(self, flow_folder):
        flow_yaml = get_yaml_file(flow_folder)
        with open(flow_yaml, "r") as fin:
            flow = Flow.deserialize(yaml.safe_load(fin))
        assert flow.outputs["content"] is not None
        assert flow.outputs["aggregate_content"] is not None
        flow.outputs = FlowValidator._ensure_outputs_valid(flow)
        print(flow.outputs)
        assert flow.outputs["content"] is not None
        assert flow.outputs.get("aggregate_content") is None

    @pytest.mark.parametrize(
        "flow_folder, inputs, index, error_type, error_message",
        [
            (
                "flow_with_list_input",
                {"key": "['hello']"},
                None,
                InputParseError,
                (
                    "Failed to parse the flow input. The value for flow input 'key' was "
                    "interpreted as JSON string since its type is 'list'. However, the value "
                    "'['hello']' is invalid for JSON parsing. Error details: (JSONDecodeError) "
                    "Expecting value: line 1 column 2 (char 1). Please make sure your inputs are properly formatted."
                ),
            ),
            (
                "flow_with_list_input",
                {"key": "['hello']"},
                0,
                InputParseError,
                (
                    "Failed to parse the flow input. The value for flow input 'key' in line 0 of input data was "
                    "interpreted as JSON string since its type is 'list'. However, the value "
                    "'['hello']' is invalid for JSON parsing. Error details: (JSONDecodeError) "
                    "Expecting value: line 1 column 2 (char 1). Please make sure your inputs are properly formatted."
                ),
            ),
        ],
    )
    def test_resolve_flow_inputs_type_json_error_for_list_type(
        self, flow_folder, inputs, index, error_type, error_message
    ):
        flow_yaml = get_yaml_file(flow_folder)
        with open(flow_yaml, "r") as fin:
            flow = Flow.deserialize(yaml.safe_load(fin))

        with pytest.raises(error_type) as exe_info:
            FlowValidator.resolve_flow_inputs_type(flow, inputs, idx=index)

        if (sys.version_info.major == 3) and (sys.version_info.minor >= 11):
            # Python >= 3.11 has a different error message
            error_msg_compare = error_message.replace("list", "ValueType.LIST")
            assert error_msg_compare in exe_info.value.message
        else:
            assert error_message == exe_info.value.message
