from typing import Any, List, Mapping

from promptflow.contracts.flow import InputAssignment, InputValueType, Node
from promptflow.executor import _input_assignment_parser
from promptflow.executor._errors import ReferenceNodeBypassed


class DAGManager:
    def __init__(self, nodes: List[Node], flow_inputs: dict):
        self._nodes = nodes
        self._flow_inputs = flow_inputs
        self._pending_nodes = {node.name: node for node in nodes}
        self._completed_nodes_outputs = {}  # node name -> output
        self._bypassed_nodes = {}  # node name -> node
        # TODO: Validate the DAG to avoid circular dependencies

    @property
    def completed_nodes_outputs(self) -> Mapping[str, Any]:
        return self._completed_nodes_outputs

    @property
    def bypassed_nodes(self) -> Mapping[str, Node]:
        return self._bypassed_nodes

    def pop_ready_nodes(self) -> List[Node]:
        """Returns a list of node names that are ready, and removes them from the list of nodes to be processed."""
        ready_nodes: List[Node] = []
        for node in self._pending_nodes.values():
            if self._is_node_ready(node):
                ready_nodes.append(node)
        for node in ready_nodes:
            del self._pending_nodes[node.name]
        return ready_nodes

    def pop_bypassable_nodes(self) -> List[Node]:
        """Returns a list of nodes that are bypassed, and removes them from the list of nodes to be processed."""
        # Confirm node should be bypassed
        bypassed_nodes: List[Node] = []
        for node in self._pending_nodes.values():
            if self._is_node_ready(node) and self._is_node_bypassable(node):
                self._bypassed_nodes[node.name] = node
                bypassed_nodes.append(node)
        for node in bypassed_nodes:
            del self._pending_nodes[node.name]
        return bypassed_nodes

    def get_node_valid_inputs(self, node: Node) -> Mapping[str, Any]:
        """Returns the valid inputs for the node, including the flow inputs, literal values and
        the outputs of completed nodes."""
        return {
            name: self._get_node_dependency_value(i)
            for name, i in (node.inputs or {}).items()
            if not self._is_node_dependency_bypassed(i)
        }

    def get_bypassed_node_outputs(self, node: Node):
        """Returns the outputs of the bypassed node."""
        outputs = None
        # Update default outputs into completed_nodes_outputs for nodes meeting the skip condition
        if self._is_skip_condition_met(node):
            outputs = self._get_node_dependency_value(node.skip.return_value)
        return outputs

    def complete_nodes(self, nodes_outputs: Mapping[str, Any]):
        """Marks nodes as completed with the mapping from node names to their outputs."""
        self._completed_nodes_outputs.update(nodes_outputs)

    def completed(self) -> bool:
        """Returns True if all nodes have been processed."""
        return all(
            node.name in self._completed_nodes_outputs or node.name in self._bypassed_nodes for node in self._nodes
        )

    def _is_node_ready(self, node: Node) -> bool:
        """Returns True if the node is ready to be executed."""
        node_dependencies = [i for i in node.inputs.values()]
        # Add skip and activate conditions as node dependencies
        if node.skip:
            node_dependencies.extend([node.skip.condition, node.skip.return_value])
        if node.activate:
            node_dependencies.append(node.activate.condition)

        for node_dependency in node_dependencies:
            if (
                node_dependency.value_type == InputValueType.NODE_REFERENCE
                and node_dependency.value not in self._completed_nodes_outputs
                and node_dependency.value not in self._bypassed_nodes
            ):
                return False
        return True

    def _is_node_bypassable(self, node: Node) -> bool:
        """Returns True if the node should be bypassed."""
        # Bypass node if the skip condition is met
        if self._is_skip_condition_met(node):
            if self._is_node_dependency_bypassed(node.skip.return_value):
                raise ReferenceNodeBypassed(
                    message_format=(
                        "The node '{reference_node_name}' referenced by '{node_name}' has been bypassed, "
                        "so the value of this node cannot be returned. Please refer to the node that "
                        "will not be bypassed as the default return value."
                    ),
                    reference_node_name=node.skip.return_value.value,
                    node_name=node.name,
                )
            skip_return = self._get_node_dependency_value(node.skip.return_value)
            # This is not a good practice, but we need to update the default output of bypassed node
            # to completed_nodes_outputs. We will remove these after skip config is deprecated.
            self.complete_nodes({node.name: skip_return})
            return True

        # Bypass node if the activate condition is not met
        if node.activate and (
            self._is_node_dependency_bypassed(node.activate.condition)
            or not self._is_condition_met(node.activate.condition, node.activate.condition_value)
        ):
            return True

        # Bypass node if all of its node reference dependencies are bypassed
        node_dependencies = [i for i in node.inputs.values() if i.value_type == InputValueType.NODE_REFERENCE]
        all_dependencies_bypassed = node_dependencies and all(
            self._is_node_dependency_bypassed(dependency) for dependency in node_dependencies
        )
        return all_dependencies_bypassed

    def _is_skip_condition_met(self, node: Node) -> bool:
        return (
            node.skip
            and not self._is_node_dependency_bypassed(node.skip.condition)
            and self._is_condition_met(node.skip.condition, node.skip.condition_value)
        )

    def _is_condition_met(self, condition: InputAssignment, condition_value) -> bool:
        condition = self._get_node_dependency_value(condition)
        return condition == condition_value

    def _get_node_dependency_value(self, node_dependency: InputAssignment):
        return _input_assignment_parser.parse_value(node_dependency, self._completed_nodes_outputs, self._flow_inputs)

    def _is_node_dependency_bypassed(self, dependency: InputAssignment) -> bool:
        """Returns True if the dependencies of the condition are bypassed."""
        # The node should not be bypassed when its dependency is bypassed by skip config and the dependency has outputs
        return (
            dependency.value_type == InputValueType.NODE_REFERENCE
            and dependency.value in self._bypassed_nodes
            and dependency.value not in self._completed_nodes_outputs
        )
