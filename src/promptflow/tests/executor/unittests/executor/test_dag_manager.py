import pytest

from promptflow.contracts.flow import ActivateCondition, InputAssignment, Node, SkipCondition
from promptflow.executor._dag_manager import DAGManager


def create_test_node(name, input, skip=None, activate=None):
    input = InputAssignment.deserialize(input)
    skip = SkipCondition.deserialize(skip) if skip else None
    activate = ActivateCondition.deserialize(activate) if activate else None
    return Node(
        name=name,
        tool="test_tool",
        connection="azure_open_ai_connection",
        inputs={"test_input": input, "test_input2": InputAssignment("hello world")},
        provider="test_provider",
        api="test_api",
        skip=skip,
        activate=activate,
    )


def pop_ready_node_names(dag_manager: DAGManager):
    return {node.name for node in dag_manager.pop_ready_nodes()}


def pop_skipped_node_names(dag_manager: DAGManager):
    return {node.name for node in dag_manager.pop_skippable_nodes()}


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

    def test_pop_skipped_nodes(self):
        nodes = [
            create_test_node(
                "node1", input="value1", skip={"when": "${inputs.text}", "is": "hello", "return": "${inputs.text}"}
            ),
            create_test_node("node2", input="${inputs.text}", activate={"when": "${inputs.text}", "is": "world"}),
            create_test_node("node3", input="${node1.output}"),
            create_test_node("node4", input="${node2.output}"),
        ]
        flow_inputs = {"text": "hello"}
        dag_manager = DAGManager(nodes, flow_inputs)
        expected_skipped_nodes = {"node1", "node2", "node4"}
        assert pop_skipped_node_names(dag_manager) == expected_skipped_nodes
        assert dag_manager.skipped_nodes.keys() == expected_skipped_nodes

    def test_complete_nodes(self):
        nodes = [create_test_node("node1", input="value1")]
        dag_manager = DAGManager(nodes, flow_inputs={})
        dag_manager.complete_nodes({"node1": {"output1": "value1"}})
        assert len(dag_manager.completed_nodes_outputs) == 1
        assert dag_manager.completed_nodes_outputs["node1"] == {"output1": "value1"}

    def test_completed(self):
        nodes = [
            create_test_node(
                "node1", input="value1", skip={"when": "${inputs.text}", "is": "hello", "return": "${inputs.text}"}
            ),
            create_test_node("node2", input="${inputs.text}", activate={"when": "${inputs.text}", "is": "hello"}),
            create_test_node("node3", input="${node1.output}"),
        ]
        flow_inputs = {"text": "hello"}
        dag_manager = DAGManager(nodes, flow_inputs)
        assert pop_skipped_node_names(dag_manager) == {"node1"}
        assert pop_ready_node_names(dag_manager) == {"node2", "node3"}
        dag_manager.complete_nodes({"node2": {"output1": "value1"}})
        dag_manager.complete_nodes({"node3": {"output1": "value1"}})
        assert dag_manager.completed_nodes_outputs.keys() == {"node1", "node2", "node3"}
        assert dag_manager.skipped_nodes.keys() == {"node1"}
        assert dag_manager.completed()

    def test_get_node_valid_inputs(self):
        nodes = [
            create_test_node("node1", input="value1"),
            create_test_node("node2", input="${node1.output}"),
        ]
        flow_inputs = {}
        dag_manager = DAGManager(nodes, flow_inputs)
        dag_manager.complete_nodes({"node1": {"output1": "value1"}})
        valid_inputs = dag_manager.get_node_valid_inputs(nodes[1])
        assert valid_inputs == {"test_input": {"output1": "value1"}, "test_input2": "hello world"}

    def test_get_skipped_node_outputs(self):
        nodes = [
            create_test_node(
                "node1", input="value1", skip={"when": "${inputs.text}", "is": "hello", "return": "${inputs.text}"}
            ),
            create_test_node("node2", input="${inputs.text}", activate={"when": "${inputs.text}", "is": "world"}),
            create_test_node("node3", input="${node1.output}"),
        ]
        flow_inputs = {"text": "hello"}
        dag_manager = DAGManager(nodes, flow_inputs)
        assert pop_skipped_node_names(dag_manager) == {"node1", "node2"}
        dag_manager.complete_nodes({"node3": {"output1": "value1"}})
        assert dag_manager.completed()
        assert dag_manager.completed_nodes_outputs.keys() == {"node1", "node3"}
        assert dag_manager.skipped_nodes.keys() == {"node1", "node2"}
        assert dag_manager.get_skipped_node_outputs(nodes[0]) == "hello"
        assert dag_manager.get_skipped_node_outputs(nodes[1]) is None
