import pytest

from promptflow._core.tools_manager import ToolsManager
from promptflow.contracts.flow import Flow, InputAssignment, InputValueType, Node
from promptflow.executor.flow_nodes_scheduler import FlowNodesSceduler


@pytest.mark.unittest
def create_test_node(name, input_value):
    return Node(
        name=name,
        tool="tool1",
        connection="azure_open_ai_connection",
        inputs={"input1": input_value},
        provider="provider1",
        api="api1",
    )


def test_subsequent_nodes_dependency():
    # Create a flow with three nodes
    node1 = create_test_node("node1", InputAssignment("value1"))
    node2 = create_test_node("node2", InputAssignment(value="node1", value_type=InputValueType.NODE_REFERENCE))
    node3 = create_test_node("node3", InputAssignment(value="node1", value_type=InputValueType.NODE_REFERENCE))
    flow = Flow(id="fakeId", name=None, nodes=[node1, node2, node3], inputs={}, outputs=None, tools=[])
    # Create a tools manager
    tools_manager = ToolsManager()
    # Create a NodeConcurrentExecutor instance
    executor = FlowNodesSceduler(flow=flow, tools_manager=tools_manager)

    # Check that the subsequent_nodes_dependency attribute is correctly populated
    assert executor.subsequent_nodes_name == {
        "node1": {"node2", "node3"},
        "node2": set(),
        "node3": set(),
    }

    node1 = create_test_node("node1", InputAssignment(value="node2", value_type=InputValueType.NODE_REFERENCE))
    node2 = create_test_node("node2", InputAssignment(value="node1", value_type=InputValueType.NODE_REFERENCE))
    flow = Flow(id="fakeId", name=None, nodes=[node1, node2], inputs={}, outputs=None, tools=[])
    executor = FlowNodesSceduler(flow=flow, tools_manager=tools_manager)
    # Will not check loop dependency.
    assert executor.subsequent_nodes_name == {
        "node1": {"node2"},
        "node2": {"node1"},
    }
