import inspect
from typing import Any, Callable, Dict, List, Mapping

from promptflow._utils.logger_utils import flow_logger
from promptflow.contracts.flow import InputAssignment, InputValueType, Node
from promptflow.executor import _input_assignment_parser


class DAGManager:
    def __init__(self, nodes: List[Node], flow_inputs: dict):
        self._nodes = nodes
        self._flow_inputs = flow_inputs
        self._pending_nodes = {node.name: node for node in nodes}
        self._completed_nodes_outputs = {}  # node name -> output
        self._bypassed_nodes = {}  # node name -> node
        # TODO: Validate the DAG to avoid circular dependencies

    @property
    def completed_nodes_outputs(self) -> Dict[str, Any]:
        return self._completed_nodes_outputs

    @property
    def bypassed_nodes(self) -> Dict[str, Node]:
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

    def get_node_valid_inputs(self, node: Node, f: Callable) -> Mapping[str, Any]:
        """Returns the valid inputs for the node, including the flow inputs, literal values and
        the outputs of completed nodes. The valid inputs are determined by the function of the node.

        :param node: The node for which to determine the valid inputs.
        :type node: Node
        :param f: The function of the current node, which is used to determine the valid inputs.
            In the case when node dependency is bypassed, the input is not required when parameter has default value,
            and the input is set to None when parameter has no default value.
        :type f: Callable
        :return: A dictionary mapping each valid input name to its value.
        :rtype: dict
        """

        results = {}
        signature = inspect.signature(f).parameters
        for name, i in (node.inputs or {}).items():
            if self._is_node_dependency_bypassed(i):
                # If the parameter has default value, the input will not be set so that the default value will be used.
                if signature.get(name) is not None and signature[name].default is not inspect.Parameter.empty:
                    continue
                # If the parameter has no default value, the input will be set to None so that function will not fail.
                else:
                    flow_logger.warning(
                        f"The node '{i.value}' referenced by the input '{name}' of the current node '{node.name}' "
                        "has been bypassed, and no default value is set. Will use 'None' as the value for this input."
                    )
                    results[name] = None
            else:
                results[name] = self._get_node_dependency_value(i)
        return results

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
        # Add activate conditions as node dependencies
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
        # Bypass node if the activate condition is not met
        if node.activate:
            # If the node referenced by activate condition is bypassed, the current node should be bypassed
            if self._is_node_dependency_bypassed(node.activate.condition):
                flow_logger.info(
                    f"The node '{node.name}' will be bypassed because it depends on the node "
                    f"'{node.activate.condition.value}' which has already been bypassed in the activate config."
                )
                return True
            # If a node has activate config, we will always use this config
            # to determine whether the node should be bypassed.
            activate_condition = InputAssignment.serialize(node.activate.condition)
            if not self._is_condition_met(node.activate.condition, node.activate.condition_value):
                flow_logger.info(
                    f"The node '{node.name}' will be bypassed because the activate condition is not met, "
                    f"i.e. '{activate_condition}' is not equal to '{node.activate.condition_value}'."
                )
                return True
            else:
                flow_logger.info(
                    f"The node '{node.name}' will be executed because the activate condition is met, "
                    f"i.e. '{activate_condition}' is equal to '{node.activate.condition_value}'."
                )
                return False

        # Bypass node if all of its node reference dependencies are bypassed
        node_dependencies = [i for i in node.inputs.values() if i.value_type == InputValueType.NODE_REFERENCE]
        all_dependencies_bypassed = node_dependencies and all(
            self._is_node_dependency_bypassed(dependency) for dependency in node_dependencies
        )
        if all_dependencies_bypassed:
            node_dependencies_list = [dependency.value for dependency in node_dependencies]
            flow_logger.info(
                f"The node '{node.name}' will be bypassed because all nodes "
                f"{node_dependencies_list} it depends on are bypassed."
            )
        return all_dependencies_bypassed

    def _is_condition_met(self, condition: InputAssignment, condition_value) -> bool:
        condition = self._get_node_dependency_value(condition)
        return condition == condition_value

    def _get_node_dependency_value(self, node_dependency: InputAssignment):
        return _input_assignment_parser.parse_value(node_dependency, self._completed_nodes_outputs, self._flow_inputs)

    def _is_node_dependency_bypassed(self, dependency: InputAssignment) -> bool:
        """Returns True if the node dependency is bypassed.

        There are two types of the node dependency:
        1. The inputs of the node
        2. The activate condition of the node
        """
        return dependency.value_type == InputValueType.NODE_REFERENCE and dependency.value in self._bypassed_nodes
