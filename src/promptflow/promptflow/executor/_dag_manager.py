from typing import Any, List, Mapping

from promptflow.contracts.flow import InputAssignment, InputValueType, Node
from promptflow.executor import _input_assignment_parser


class DAGManager:
    def __init__(self, nodes: List[Node], flow_inputs: dict):
        self._nodes = nodes
        self._flow_inputs = flow_inputs
        self._pending_nodes = {node.name: node for node in nodes}
        self._completed_nodes_outputs = {}  # node name -> output
        self._skipped_nodes = {}  # node name -> node
        # TODO: Validate the DAG to avoid circular dependencies

    @property
    def completed_nodes_outputs(self) -> Mapping[str, Any]:
        return self._completed_nodes_outputs

    @property
    def skipped_nodes(self) -> Mapping[str, Node]:
        return self._skipped_nodes

    def pop_ready_nodes(self) -> List[Node]:
        """Returns a list of node names that are ready, and removes them from the list of nodes to be processed."""
        ready_nodes: List[Node] = []
        for node in self._pending_nodes.values():
            if self._is_node_ready(node):
                ready_nodes.append(node)
        for node in ready_nodes:
            del self._pending_nodes[node.name]
        return ready_nodes

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

    def get_node_valid_inputs(self, node: Node) -> Mapping[str, Any]:
        return {
            name: self._get_node_dependency_value(i)
            for name, i in (node.inputs or {}).items()
            if not self._is_node_dependency_skipped(i)
        }

    def get_skipped_node_outputs(self, node: Node):
        """Returns the outputs of the skipped node."""
        outputs = None
        # Update default outputs into completed_nodes_outputs for nodes meeting the skip condition
        if self._is_skip_condition_met(node):
            outputs = self._get_node_dependency_value(node.skip.return_value)
            self.complete_nodes({node.name: outputs})
        return outputs

    def complete_nodes(self, nodes_outputs: Mapping[str, Any]):
        """Marks nodes as completed with the mapping from node names to their outputs."""
        self._completed_nodes_outputs.update(nodes_outputs)

    def completed(self) -> bool:
        """Returns True if all nodes have been processed."""
        return all(
            node.name in self._completed_nodes_outputs
            or node.name in self._skipped_nodes
            for node in self._nodes
        )

    def _is_node_ready(self, node: Node) -> bool:
        """Returns True if the node is ready to be executed."""
        node_dependencies = [i for i in node.inputs.values()]
        for node_dependency in node_dependencies:
            if (
                node_dependency.value_type == InputValueType.NODE_REFERENCE
                and node_dependency.value not in self._completed_nodes_outputs
                and node_dependency.value not in self._skipped_nodes
            ):
                return False
        return True

    def _is_node_skipped(self, node: Node) -> bool:
        """Returns True if the node should be skipped."""
        # Skip node if the skip condition is met
        if self._is_skip_condition_met(node):
            return True

        # Skip node if the activate condition is not met
        if node.activate:
            if self._is_node_dependency_skipped(node.activate.condition):
                return True
            activate_condition = self._get_node_dependency_value(node.activate.condition)
            if activate_condition != node.activate.condition_value:
                return True

        # Skip node if all of its node reference dependencies are skipped
        node_dependencies = [i for i in node.inputs.values() if i.value_type == InputValueType.NODE_REFERENCE]
        all_dependencies_skipped = node_dependencies and all(
            self._is_node_dependency_skipped(dependency)
            for dependency in node_dependencies
        )
        return all_dependencies_skipped

    def _is_skip_condition_met(self, node: Node) -> bool:
        if node.skip and not self._is_node_dependency_skipped(node.skip.condition):
            skip_condition = self._get_node_dependency_value(node.skip.condition)
            if skip_condition == node.skip.condition_value:
                return True
        return False

    def _get_node_dependency_value(self, node_dependency: InputAssignment):
        return _input_assignment_parser.parse_value(node_dependency, self._completed_nodes_outputs, self._flow_inputs)

    def _is_node_dependency_skipped(self, dependency: InputAssignment) -> bool:
        """Returns True if the dependencies of the condition are skipped."""
        # The node should not be skipped when its dependency is skipped by skip config and the dependency has outputs
        return (
            dependency.value_type == InputValueType.NODE_REFERENCE
            and dependency.value in self._skipped_nodes
            and dependency.value not in self._completed_nodes_outputs
        )
