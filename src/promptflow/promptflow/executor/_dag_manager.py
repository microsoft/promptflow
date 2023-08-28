from typing import Any, List, Mapping

from promptflow.contracts.flow import InputAssignment, InputValueType, Node
from promptflow.executor import _input_assignment_parser


class DAGManager:
    def __init__(self, nodes: List[Node], flow_inputs: dict):
        self._nodes = nodes
        self._flow_inputs = flow_inputs
        self._pending_nodes = {node.name: node for node in nodes}
        self._should_completed_nodes = self._pending_nodes.copy()
        self._completed_nodes_outputs = {}  # node name -> output
        self._skipped_nodes = {}
        # TODO: Validate the DAG to avoid circular dependencies

    @property
    def completed_nodes_outputs(self) -> Mapping[str, Any]:
        return self._completed_nodes_outputs

    def pop_ready_nodes(self) -> List[Node]:
        """Returns a list of node names that are ready, and removes them from the list of nodes to be processed."""
        ready_nodes: List[Node] = []
        for node in self._pending_nodes.values():
            if self._is_node_ready(node):
                ready_nodes.append(node)
        for node in ready_nodes:
            del self._pending_nodes[node.name]
        return ready_nodes

    def _is_node_ready(self, node: Node) -> bool:
        """Returns True if the node is ready to be executed."""
        node_dependencies = [i for i in node.inputs.values()]
        for node_dependency in node_dependencies:
            if node_dependency.value_type == InputValueType.NODE_REFERENCE and \
                    node_dependency.value not in self._completed_nodes_outputs and \
                    node_dependency.value not in self._skipped_nodes:
                return False
        return True

    def pop_skipped_nodes(self) -> List[Node]:
        """Returns a list of nodes that are skipped, and removes them from the list of nodes to be processed."""
        # Confirm node should be skipped
        skipped_nodes: List[Node] = []
        for node in self._pending_nodes.values():
            if self._is_node_ready(node) and self._is_node_skipped(node):
                self._skipped_nodes[node.name] = node
                skipped_nodes.append(node)
        for node in skipped_nodes:
            del self._pending_nodes[node.name]
        return skipped_nodes

    def _is_node_skipped(self, node: Node) -> bool:
        """Returns True if the node should be skipped."""
        # Skip node if the skip condition is met
        if node.skip:
            if self._is_node_dependency_skipped(node.skip.condition):
                return True
            skip_condition = _input_assignment_parser.parse_value(
                node.skip.condition, self._completed_nodes_outputs, self._flow_inputs)
            if skip_condition == node.skip.condition_value:
                return True

        # Skip node if the activate condition is not met
        if node.activate:
            if self._is_node_dependency_skipped(node.activate.condition):
                return True
            activate_condition = _input_assignment_parser.parse_value(
                node.activate.condition, self._completed_nodes_outputs, self._flow_inputs)
            if activate_condition != node.activate.condition_value:
                del self._should_completed_nodes[node.name]
                return True

        # Skip node if all of its dependencies are skipped
        node_dependencies = [i for i in node.inputs.values()]
        if not node_dependencies:
            # If the node has no dependencies, it should be executed
            return False

        all_dependencies_skipped = all(self._is_node_dependency_skipped(node_dependency)
                                       for node_dependency in node_dependencies)
        if all_dependencies_skipped:
            del self._should_completed_nodes[node.name]
            return True

        return False

    def _is_node_dependency_skipped(self, dependency: InputAssignment) -> bool:
        """Returns True if the dependencies of the condition are skipped."""
        return dependency.value_type == InputValueType.NODE_REFERENCE and dependency.value in self._skipped_nodes

    def complete_nodes(self, nodes_outputs: Mapping[str, Any]):
        """Marks nodes as completed with the mapping from node names to their outputs."""
        self._completed_nodes_outputs.update(nodes_outputs)

    def completed(self) -> bool:
        """Returns True if all nodes have been processed."""
        return len(self._completed_nodes_outputs) == len(self._should_completed_nodes)
