from typing import Any, List, Mapping

from promptflow.contracts.flow import InputValueType, Node


class DAGManager:
    def __init__(self, nodes: List[Node]):
        self._nodes = nodes
        self._pending_nodes = {node.name: node for node in nodes}
        self._completed_nodes_outputs = {}  # node name -> output
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
        if node.skip:
            node_dependencies.extend([node.skip.condition, node.skip.return_value])
        for node_dependency in node_dependencies:
            if node_dependency.value_type == InputValueType.NODE_REFERENCE:
                if node_dependency.value not in self._completed_nodes_outputs:
                    return False
        return True

    def pop_skipped_nodes(self) -> List[Node]:
        """Returns a list of nodes that are skipped, and removes them from the list of nodes to be processed."""
        #  TODO: implement this
        return set()

    def complete_nodes(self, nodes_outputs: Mapping[str, Any]):
        """Marks nodes as completed with the mapping from node names to their outputs."""
        self._completed_nodes_outputs.update(nodes_outputs)

    def completed(self) -> bool:
        """Returns True if all nodes have been processed."""
        return len(self._completed_nodes_outputs) == len(self._nodes)
