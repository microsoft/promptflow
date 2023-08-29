from pathlib import Path

import pytest
import yaml

from promptflow.contracts.flow import Flow
from promptflow.executor._errors import InvalidFlowRequest
from promptflow.executor._flow_validator import FlowValidator

TEST_ROOT = Path(__file__).parent.parent.parent.parent
REQUESTS_PATH = TEST_ROOT / "test_configs/flows/"
WRONG_REQUESTS_PATH = TEST_ROOT / "test_configs/wrong_flows/"


@pytest.mark.unittest
class TestFlowValidator:
    @pytest.mark.parametrize(
        "file_name, expected_node_order",
        [
            ("unordered_nodes/out_of_order_nodes.dag.yaml", ["first_node", "second_node", "third_node"]),
            (
                "unordered_nodes_with_skip/out_of_order_nodes_with_skip.dag.yaml",
                ["first_node", "second_node", "third_node"],
            ),
        ],
    )
    def test_ensure_nodes_order(self, file_name, expected_node_order):
        flow_file_path = Path(REQUESTS_PATH) / file_name
        flow_file_path = flow_file_path.resolve().absolute()
        with open(flow_file_path, "r") as fin:
            flow = Flow.deserialize(yaml.safe_load(fin))
        flow = FlowValidator._ensure_nodes_order(flow)
        node_order = [node.name for node in flow.nodes]
        assert node_order == expected_node_order

    @pytest.mark.parametrize(
        "file_name, error_message",
        [
            ("nodes_cycle/node_cycle.dag.yaml", "There is a circular dependency in the flow 'node_cycle'."),
            (
                "nodes_cycle_with_skip/node_cycle_with_skip.dag.yaml",
                "There is a circular dependency in the flow 'node_cycle_with_skip'.",
            ),
            (
                "wrong_node_reference/node_wrong_reference.dag.yaml",
                "Node 'second_node' references node 'third_node' which is not in the flow 'node_wrong_reference'.",
            ),
        ],
    )
    def test_ensure_nodes_order_with_exception(self, file_name, error_message):
        flow_file_path = Path(WRONG_REQUESTS_PATH) / file_name
        flow_file_path = flow_file_path.resolve().absolute()
        with open(flow_file_path, "r") as fin:
            flow = Flow.deserialize(yaml.safe_load(fin))
        with pytest.raises(InvalidFlowRequest) as e:
            FlowValidator._ensure_nodes_order(flow)
        assert str(e.value) == error_message, "Expected: {}, Actual: {}".format(error_message, str(e.value))

    @pytest.mark.parametrize(
        "file_name",
        ["simple_flow_with_python_tool_and_aggregate/flow.dag.yaml"],
    )
    def test_ensure_outputs_valid_with_aggregation(self, file_name):
        flow_file_path = Path(REQUESTS_PATH) / file_name
        flow_file_path = flow_file_path.resolve().absolute()
        with open(flow_file_path, "r") as fin:
            flow = Flow.deserialize(yaml.safe_load(fin))
        assert flow.outputs["content"] is not None
        assert flow.outputs["aggregate_content"] is not None
        flow.outputs = FlowValidator._ensure_outputs_valid(flow)
        print(flow.outputs)
        assert flow.outputs["content"] is not None
        assert flow.outputs.get("aggregate_content") is None
