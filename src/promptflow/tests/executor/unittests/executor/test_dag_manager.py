import pytest

from promptflow.contracts.flow import InputAssignment, InputValueType, Node
from promptflow.executor._dag_manager import DAGManager


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


def pop_ready_node_names(dag_manager: DAGManager):
    return {node.name for node in dag_manager.pop_ready_nodes()}


def test_dag_manager_operations():
    # Create a flow with three nodes
    node1 = create_test_node("node1", InputAssignment("value1"))
    node2 = create_test_node("node2", InputAssignment(value="node1", value_type=InputValueType.NODE_REFERENCE))
    node3 = create_test_node("node3", InputAssignment(value="node1", value_type=InputValueType.NODE_REFERENCE))
    dag_manager = DAGManager([node1, node2, node3], flow_inputs={})
    assert pop_ready_node_names(dag_manager) == {"node1"}
    dag_manager.complete_nodes({"node1": None})
    assert not dag_manager.completed()
    assert pop_ready_node_names(dag_manager) == {"node2", "node3"}
    assert not dag_manager.completed()
    dag_manager.complete_nodes({"node2": None, "node3": None})
    assert dag_manager.completed()

    node1 = create_test_node("node1", InputAssignment(value="node2", value_type=InputValueType.NODE_REFERENCE))
    node2 = create_test_node("node2", InputAssignment(value="node1", value_type=InputValueType.NODE_REFERENCE))
    # DAG Manager doesn't handle circular dependencies now
    dag_manager = DAGManager([node1, node2], flow_inputs={})
    assert pop_ready_node_names(dag_manager) == set()
    assert not dag_manager.completed()
