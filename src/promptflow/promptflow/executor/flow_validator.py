# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import copy
from typing import Any, Mapping, Optional

from promptflow._utils.logger_utils import logger
from promptflow.contracts.flow import Flow, InputValueType, Node
from promptflow.executor._errors import (
    DuplicateNodeName,
    EmptyOutputReference,
    InputNotFound,
    InputReferenceNotFound,
    InputTypeError,
    NodeCircularDependency,
    NodeReferenceNotFound,
    OutputReferenceNotFound,
)


class FlowValidator:
    """This is a validation class designed to verify the integrity and validity of flow definitions and input data."""

    @staticmethod
    def _ensure_nodes_order(flow: Flow):
        dependencies = {n.name: set() for n in flow.nodes}
        for n in flow.nodes:
            inputs_list = [i for i in n.inputs.values()]
            if n.skip:
                inputs_list.extend([n.skip.condition, n.skip.return_value])
            if n.activate:
                inputs_list.extend([n.activate.condition])
            for i in inputs_list:
                if i.value_type != InputValueType.NODE_REFERENCE:
                    continue
                if i.value not in dependencies:
                    msg_format = (
                        "Invalid node definitions found in the flow graph. Node '{node_name}' references "
                        "a non-existent node '{reference_node_name}' in your flow. Please review your flow to "
                        "ensure that the node name is accurately specified."
                    )
                    raise NodeReferenceNotFound(
                        message_format=msg_format, node_name=n.name, reference_node_name=i.value
                    )
                dependencies[n.name].add(i.value)
        sorted_nodes = []
        picked = set()
        for _ in range(len(flow.nodes)):
            available_nodes_iterator = (
                n for n in flow.nodes if n.name not in picked and all(d in picked for d in dependencies[n.name])
            )
            node_to_pick = next(available_nodes_iterator, None)
            if not node_to_pick:
                # Figure out the nodes names with circular dependency problem alphabetically
                remaining_nodes = sorted(list(set(dependencies.keys()) - picked))
                raise NodeCircularDependency(
                    message_format=(
                        "Invalid node definitions found in the flow graph. Node circular dependency has been detected "
                        "among the nodes in your flow. Kindly review the reference relationships for the nodes "
                        "{remaining_nodes} and resolve the circular reference issue in the flow."
                    ),
                    remaining_nodes=remaining_nodes,
                )
            sorted_nodes.append(node_to_pick)
            picked.add(node_to_pick.name)
        if any(n1.name != n2.name for n1, n2 in zip(flow.nodes, sorted_nodes)):
            return Flow(
                id=flow.id,
                name=flow.name,
                nodes=sorted_nodes,
                inputs=flow.inputs,
                outputs=flow.outputs,
                tools=flow.tools,
            )
        return copy.copy(flow)

    @staticmethod
    def _validate_nodes_topology(flow: Flow) -> Flow:
        node_names = set()
        for node in flow.nodes:
            if node.name in node_names:
                raise DuplicateNodeName(
                    message_format=(
                        "Invalid node definitions found in the flow graph. Node with name '{node_name}' appears "
                        "more than once in the node definitions in your flow, which is not allowed. To address "
                        "this issue, please review your flow and either rename or remove nodes with identical names."
                    ),
                    node_name=node.name,
                )
            node_names.add(node.name)
        for node in flow.nodes:
            for v in node.inputs.values():
                if v.value_type != InputValueType.FLOW_INPUT:
                    continue
                if v.value not in flow.inputs:
                    msg_format = (
                        "Invalid node definitions found in the flow graph. Node '{node_name}' references flow input "
                        "'{flow_input_name}' which is not defined in your flow. To resolve this issue, "
                        "please review your flow, ensuring that you either add the missing flow inputs "
                        "or adjust node reference to the correct flow input."
                    )
                    raise InputReferenceNotFound(
                        message_format=msg_format, node_name=node.name, flow_input_name=v.value
                    )
        return FlowValidator._ensure_nodes_order(flow)

    @staticmethod
    def resolve_flow_inputs_type(flow: Flow, inputs: Mapping[str, Any], idx: Optional[int] = None) -> Mapping[str, Any]:
        """Resolve inputs by type if existing. Ignore missing inputs.

        :param flow: The `flow` parameter is of type `Flow` and represents a flow object
        :type flow: ~promptflow.contracts.flow.Flow
        :param inputs: A dictionary containing the input values for the flow. The keys are the names of the
            flow inputs, and the values are the corresponding input values
        :type inputs: Mapping[str, Any]
        :param idx: The `idx` parameter is an optional integer that represents the line index of the input
            data. It is used to provide additional information in case there is an error with the input data
        :type idx: Optional[int]
        :return: The updated inputs with values are type-converted based on the expected type specified
            in the `flow` object.
        :rtype: Mapping[str, Any]
        """
        updated_inputs = {k: v for k, v in inputs.items()}
        for k, v in flow.inputs.items():
            try:
                if k in inputs:
                    updated_inputs[k] = v.type.parse(inputs[k])
            except Exception as e:
                line_info = "" if idx is None else f"in line {idx} of input data"
                msg_format = (
                    "The input for flow is incorrect. The value for flow input '{flow_input_name}' {line_info} "
                    "does not match the expected type '{expected_type}'. Please change flow input type "
                    "or adjust the input value in your input data."
                )
                raise InputTypeError(
                    message_format=msg_format, flow_input_name=k, line_info=line_info, expected_type=v.type
                ) from e
        return updated_inputs

    @staticmethod
    def ensure_flow_inputs_type(flow: Flow, inputs: Mapping[str, Any], idx: Optional[int] = None) -> Mapping[str, Any]:
        """Make sure the inputs are completed and in the correct type. Raise Exception if not valid.

        :param flow: The `flow` parameter is of type `Flow` and represents a flow object
        :type flow: ~promptflow.contracts.flow.Flow
        :param inputs: A dictionary containing the input values for the flow. The keys are the names of the
            flow inputs, and the values are the corresponding input values
        :type inputs: Mapping[str, Any]
        :param idx: The `idx` parameter is an optional integer that represents the line index of the input
            data. It is used to provide additional information in case there is an error with the input data
        :type idx: Optional[int]
        :return: The updated inputs, where the values are type-converted based on the expected
            type specified in the `flow` object.
        :rtype: Mapping[str, Any]
        """
        for k, v in flow.inputs.items():
            if k not in inputs:
                line_info = "in input data" if idx is None else f"in line {idx} of input data"
                msg_format = (
                    "The input for flow is incorrect. The value for flow input '{input_name}' is not "
                    "provided {line_info}. Please review your input data or remove this input in your flow "
                    "if it's no longer needed."
                )
                raise InputNotFound(message_format=msg_format, input_name=k, line_info=line_info)
        return FlowValidator.resolve_flow_inputs_type(flow, inputs, idx)

    @staticmethod
    def convert_flow_inputs_for_node(flow: Flow, node: Node, inputs: Mapping[str, Any]) -> Mapping[str, Any]:
        """Filter the flow inputs for node and resolve the value by type.

        :param flow: The `flow` parameter is an instance of the `Flow` class. It represents the flow or
            workflow that contains the node and inputs
        :type flow: ~promptflow.contracts.flow.Flow
        :param node: The `node` parameter is an instance of the `Node` class
        :type node: ~promptflow.contracts.flow.Node
        :param inputs: A dictionary containing the input values for the node. The keys are the names of the
            input variables, and the values are the corresponding input values
        :type inputs: Mapping[str, Any]
        :return: the resolved flow inputs which are needed by the node only by the node only.
        :rtype: Mapping[str, Any]
        """
        updated_inputs = {}
        inputs = inputs or {}
        for k, v in node.inputs.items():
            if v.value_type == InputValueType.FLOW_INPUT:
                if v.value not in flow.inputs:
                    raise InputNotFound(
                        message_format=(
                            "The input for node is incorrect. Node input '{node_input_name}' is not found "
                            "from flow inputs of node '{node_name}'. Please review the node definition in your flow."
                        ),
                        node_input_name=v.value,
                        node_name=node.name,
                    )
                if v.value not in inputs:
                    raise InputNotFound(
                        message_format=(
                            "The input for node is incorrect. Node input '{node_input_name}' is not found "
                            "in input data for node '{node_name}'. Please verify the inputs data for the node."
                        ),
                        node_input_name=v.value,
                        node_name=node.name,
                    )
                try:
                    updated_inputs[v.value] = flow.inputs[v.value].type.parse(inputs[v.value])
                except Exception as e:
                    msg_format = (
                        "The input for node is incorrect. Value for input '{input_name}' of node '{node_name}' "
                        "is not type '{expected_type}'. Please review and rectify the input data."
                    )
                    raise InputTypeError(
                        message_format=msg_format,
                        input_name=k,
                        node_name=node.name,
                        expected_type=flow.inputs[v.value].type,
                    ) from e
        return updated_inputs

    @staticmethod
    def _ensure_outputs_valid(flow: Flow):
        updated_outputs = {}
        for k, v in flow.outputs.items():
            if v.reference.value_type == InputValueType.LITERAL and v.reference.value == "":
                msg_format = (
                    "The output '{output_name}' for flow is incorrect. The reference is not specified for "
                    "the output '{output_name}' in the flow. To rectify this, "
                    "ensure that you accurately specify the reference in the flow."
                )
                raise EmptyOutputReference(message_format=msg_format, output_name=k)
            if v.reference.value_type == InputValueType.FLOW_INPUT and v.reference.value not in flow.inputs:
                msg_format = (
                    "The output '{output_name}' for flow is incorrect. The output '{output_name}' references "
                    "non-existent flow input '{flow_input_name}' in your flow. Please carefully review your flow and "
                    "correct the reference definition for the output in question."
                )
                raise OutputReferenceNotFound(
                    message_format=msg_format, output_name=k, flow_input_name=v.reference.value
                )
            if v.reference.value_type == InputValueType.NODE_REFERENCE:
                node = flow.get_node(v.reference.value)
                if node is None:
                    msg_format = (
                        "The output '{output_name}' for flow is incorrect. The output '{output_name}' references "
                        "non-existent node '{node_name}' in your flow. To resolve this issue, please carefully review "
                        "your flow and correct the reference definition for the output in question."
                    )
                    raise OutputReferenceNotFound(message_format=msg_format, output_name=k, node_name=v.reference.value)
                if node.aggregation:
                    msg = f"Output '{k}' references a reduce node '{v.reference.value}', will not take effect."
                    logger.warning(msg)
                    #  We will not add this output to the flow outputs, so we simply ignore it here
                    continue
            updated_outputs[k] = v
        return updated_outputs
