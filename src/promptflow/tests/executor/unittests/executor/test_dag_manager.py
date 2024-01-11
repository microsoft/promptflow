import pytest

from promptflow.contracts.flow import ActivateCondition, InputAssignment, Node
from promptflow.executor._dag_manager import DAGManager


def create_test_node(name, input, activate=None):
    input = InputAssignment.deserialize(input)
    activate = ActivateCondition.deserialize(activate, name) if activate else None
    return Node(
        name=name,
        tool="test_tool",
        connection="azure_open_ai_connection",
        inputs={"test_input": input, "test_input2": InputAssignment("hello world")},
        provider="test_provider",
        api="test_api",
        activate=activate,
    )


def pop_ready_node_names(dag_manager: DAGManager):
    return {node.name for node in dag_manager.pop_ready_nodes()}


def pop_bypassed_node_names(dag_manager: DAGManager):
    return {node.name for node in dag_manager.pop_bypassable_nodes()}


@pytest.mark.unittest
class TestDAGManager:
    def test_pop_ready_nodes(self):
        nodes = [
            create_test_node("node1", input="value1"),
            create_test_node("node2", input="${node1.output}"),
            create_test_node("node3", input="${node1.output}"),
        ]
        dag_manager = DAGManager(nodes, flow_inputs={})
        assert pop_ready_node_names(dag_manager) == {"node1"}
        dag_manager.complete_nodes({"node1": None})
        assert pop_ready_node_names(dag_manager) == {"node2", "node3"}
        dag_manager.complete_nodes({"node2": None, "node3": None})

    def test_pop_bypassed_nodes(self):
        nodes = [
            create_test_node("node1", input="value1"),
            create_test_node("node2", input="${inputs.text}", activate={"when": "${inputs.text}", "is": "world"}),
            create_test_node("node3", input="${node1.output}"),
            create_test_node("node4", input="${node2.output}"),
        ]
        flow_inputs = {"text": "hello"}
        dag_manager = DAGManager(nodes, flow_inputs)
        expected_bypassed_nodes = {"node2", "node4"}
        assert pop_bypassed_node_names(dag_manager) == expected_bypassed_nodes
        assert dag_manager.bypassed_nodes.keys() == expected_bypassed_nodes

    def test_complete_nodes(self):
        nodes = [create_test_node("node1", input="value1")]
        dag_manager = DAGManager(nodes, flow_inputs={})
        dag_manager.complete_nodes({"node1": {"output1": "value1"}})
        assert len(dag_manager.completed_nodes_outputs) == 1
        assert dag_manager.completed_nodes_outputs["node1"] == {"output1": "value1"}

    def test_completed(self):
        nodes = [
            create_test_node("node1", input="${inputs.text}", activate={"when": "${inputs.text}", "is": "hello"}),
            create_test_node("node2", input="${node1.output}"),
        ]
        flow_inputs = {"text": "hello"}
        dag_manager = DAGManager(nodes, flow_inputs)
        assert pop_ready_node_names(dag_manager) == {"node1"}
        dag_manager.complete_nodes({"node1": {"output1": "value1"}})
        assert pop_ready_node_names(dag_manager) == {"node2"}
        dag_manager.complete_nodes({"node2": {"output1": "value1"}})
        assert dag_manager.completed_nodes_outputs.keys() == {"node1", "node2"}
        assert dag_manager.completed()

    def test_get_node_valid_inputs(self):
        nodes = [
            create_test_node("node1", input="value1"),
            create_test_node("node2", input="${node1.output}"),
        ]

        def f(input):
            return input

        flow_inputs = {}
        dag_manager = DAGManager(nodes, flow_inputs)
        dag_manager.complete_nodes({"node1": {"output1": "value1"}})
        valid_inputs = dag_manager.get_node_valid_inputs(nodes[1], f)
        assert valid_inputs == {"test_input": {"output1": "value1"}, "test_input2": "hello world"}
