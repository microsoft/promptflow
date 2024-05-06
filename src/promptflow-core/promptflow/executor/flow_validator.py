# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import copy
from json import JSONDecodeError
from typing import Any, List, Mapping, Optional

from promptflow._utils.logger_utils import logger
from promptflow.contracts.flow import Flow, FlowInputDefinition, InputValueType, Node
from promptflow.contracts.tool import ValueType
from promptflow.executor._errors import (
    DuplicateNodeName,
    EmptyOutputReference,
    InputNotFound,
    InputParseError,
    InputReferenceNotFound,
    InputTypeError,
    InvalidAggregationInput,
    InvalidNodeReference,
    NodeCircularDependency,
    NodeReferenceNotFound,
    OutputReferenceNotFound,
)


class FlowValidator:
    """This is a validation class designed to verify the integrity and validity of flow definitions and input data."""

    @staticmethod
    def _ensure_nodes_order(flow: Flow):
        dependencies = {n.name: set() for n in flow.nodes}
        aggregation_nodes = set(node.name for node in flow.nodes if node.aggregation)
        for n in flow.nodes:
            inputs_list = [i for i in n.inputs.values()]
            if n.activate:
                if (
                    n.aggregation
                    and n.activate.condition.value_type == InputValueType.NODE_REFERENCE
                    and n.activate.condition.value not in aggregation_nodes
                ):
                    msg_format = (
                        "Invalid node definitions found in the flow graph. Non-aggregation node '{invalid_reference}' "
                        "cannot be referenced in the activate config of the aggregation node '{node_name}'. Please "
                        "review and rectify the node reference."
                    )
                    raise InvalidNodeReference(
                        message_format=msg_format, invalid_reference=n.activate.condition.value, node_name=n.name
                    )
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
            if not n.aggregation:
                invalid_reference = dependencies[n.name].intersection(aggregation_nodes)
                if invalid_reference:
                    msg_format = (
                        "Invalid node definitions found in the flow graph. Non-aggregate node '{node_name}' "
                        "cannot reference aggregate nodes {invalid_reference}. Please review and rectify "
                        "the node reference."
                    )
                    raise InvalidNodeReference(
                        message_format=msg_format, node_name=n.name, invalid_reference=invalid_reference
                    )

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
    def _parse_input_value(input_key: str, input_value: Any, expected_type: ValueType, idx=None):
        try:
            return expected_type.parse(input_value)
        except JSONDecodeError as e:
            line_info = "" if idx is None else f" in line {idx} of input data"
            flow_input_info = f"'{input_key}'{line_info}"
            error_type_and_message = f"({e.__class__.__name__}) {e}"

            msg_format = (
                "Failed to parse the flow input. The value for flow input {flow_input_info} "
                "was interpreted as JSON string since its type is '{value_type}'. However, the value "
                "'{input_value}' is invalid for JSON parsing. Error details: {error_type_and_message}. "
                "Please make sure your inputs are properly formatted."
            )
            raise InputParseError(
                message_format=msg_format,
                flow_input_info=flow_input_info,
                input_value=input_value,
                value_type=expected_type.value if hasattr(expected_type, "value") else expected_type,
                error_type_and_message=error_type_and_message,
            ) from e
        except Exception as e:
            line_info = "" if idx is None else f" in line {idx} of input data"
            flow_input_info = f"'{input_key}'{line_info}"
            msg_format = (
                "The input for flow is incorrect. The value for flow input {flow_input_info} "
                "does not match the expected type '{expected_type}'. Please change flow input type "
                "or adjust the input value in your input data."
            )
            expected_type_value = expected_type.value if hasattr(expected_type, "value") else expected_type
            raise InputTypeError(
                message_format=msg_format, flow_input_info=flow_input_info, expected_type=expected_type_value
            ) from e

    @staticmethod
    def resolve_aggregated_flow_inputs_type(flow: Flow, inputs: Mapping[str, List[Any]]) -> Mapping[str, Any]:
        updated_inputs = {}
        for input_key, input_def in flow.inputs.items():
            if input_key in inputs:
                input_value_list = inputs[input_key]
                updated_inputs[input_key] = [
                    FlowValidator._parse_input_value(input_key, each_line_item, input_def.type, idx)
                    for idx, each_line_item in enumerate(input_value_list)
                ]
        return updated_inputs

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
        return FlowValidator._resolve_flow_inputs_type_inner(flow.inputs, inputs, idx)

    @staticmethod
    def _resolve_flow_inputs_type_inner(
        flow_inputs: FlowInputDefinition, inputs: Mapping[str, Any], idx: Optional[int] = None
    ) -> Mapping[str, Any]:
        updated_inputs = {k: v for k, v in inputs.items()}
        for k, v in flow_inputs.items():
            if k in inputs:
                updated_inputs[k] = FlowValidator._parse_input_value(k, inputs[k], v.type, idx)
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
        return FlowValidator._ensure_flow_inputs_type_inner(flow.inputs, inputs, idx)

    @staticmethod
    def _ensure_flow_inputs_type_inner(
        flow_inputs: FlowInputDefinition, inputs: Mapping[str, Any], idx: Optional[int] = None
    ) -> Mapping[str, Any]:
        for k, _ in flow_inputs.items():
            if k not in inputs:
                line_info = "in input data" if idx is None else f"in line {idx} of input data"
                msg_format = (
                    "The input for flow is incorrect. The value for flow input '{input_name}' is not "
                    "provided {line_info}. Please review your input data or remove this input in your flow "
                    "if it's no longer needed."
                )
                raise InputNotFound(message_format=msg_format, input_name=k, line_info=line_info)
        return FlowValidator._resolve_flow_inputs_type_inner(flow_inputs, inputs, idx)

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
                        expected_type=flow.inputs[v.value].type.value,
                    ) from e
        return updated_inputs

    @staticmethod
    def _validate_aggregation_inputs(aggregated_flow_inputs: Mapping[str, Any], aggregation_inputs: Mapping[str, Any]):
        """Validate the aggregation inputs according to the flow inputs."""
        for key, value in aggregated_flow_inputs.items():
            if key in aggregation_inputs:
                raise InvalidAggregationInput(
                    message_format=(
                        "The input for aggregation is incorrect. The input '{input_key}' appears in both "
                        "aggregated flow input and aggregated reference input. "
                        "Please remove one of them and try the operation again."
                    ),
                    input_key=key,
                )
            if not isinstance(value, list):
                raise InvalidAggregationInput(
                    message_format=(
                        "The input for aggregation is incorrect. "
                        "The value for aggregated flow input '{input_key}' should be a list, "
                        "but received {value_type}. Please adjust the input value to match the expected format."
                    ),
                    input_key=key,
                    value_type=type(value).__name__,
                )

        for key, value in aggregation_inputs.items():
            if not isinstance(value, list):
                raise InvalidAggregationInput(
                    message_format=(
                        "The input for aggregation is incorrect. "
                        "The value for aggregated reference input '{input_key}' should be a list, "
                        "but received {value_type}. Please adjust the input value to match the expected format."
                    ),
                    input_key=key,
                    value_type=type(value).__name__,
                )

        inputs_len = {key: len(value) for key, value in aggregated_flow_inputs.items()}
        inputs_len.update({key: len(value) for key, value in aggregation_inputs.items()})
        if len(set(inputs_len.values())) > 1:
            raise InvalidAggregationInput(
                message_format=(
                    "The input for aggregation is incorrect. "
                    "The length of all aggregated inputs should be the same. Current input lengths are: "
                    "{key_len}. Please adjust the input value in your input data."
                ),
                key_len=inputs_len,
            )

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

    @staticmethod
    def ensure_flow_valid_in_batch_mode(flow: Flow):
        if not flow.inputs:
            message = (
                "The input for flow cannot be empty in batch mode. Please review your flow and provide valid inputs."
            )
            raise InputNotFound(message=message)
