import pytest
import yaml

from promptflow.contracts.flow import Flow
from promptflow.executor._errors import InvalidFlowRequest
from promptflow.executor.flow_validator import FlowValidator

from ...utils import get_yaml_file, WRONG_FLOW_ROOT


@pytest.mark.unittest
class TestFlowValidator:
    @pytest.mark.parametrize(
        "flow_folder, expected_node_order",
        [
            ("unordered_nodes", ["first_node", "second_node", "third_node"]),
            ("unordered_nodes_with_skip", ["first_node", "second_node", "third_node"]),
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
                "There is a circular dependency in the flow 'node_cycle'."
            ),
            (
                "nodes_cycle_with_skip",
                "There is a circular dependency in the flow 'node_cycle_with_skip'.",
            ),
            (
                "wrong_node_reference",
                "Node 'second_node' references node 'third_node' which is not in the flow 'node_wrong_reference'.",
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
