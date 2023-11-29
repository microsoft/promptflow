# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import re

from promptflow._core._errors import NotSupported
from promptflow.contracts.flow import InputAssignment, InputValueType
from promptflow.executor._errors import (
    InputNotFound,
    InputNotFoundFromAncestorNodeOutput,
    InvalidReferenceProperty,
    UnsupportedReference,
)


def parse_value(i: InputAssignment, nodes_outputs: dict, flow_inputs: dict):
    if i.value_type == InputValueType.LITERAL:
        return i.value
    if i.value_type == InputValueType.FLOW_INPUT:
        if i.value not in flow_inputs:
            flow_input_keys = ", ".join(flow_inputs.keys()) if flow_inputs is not None else None
            raise InputNotFound(
                message_format=(
                    "Flow execution failed. "
                    "The input '{input_name}' is not found from flow inputs '{flow_input_keys}'. "
                    "Please check the input name and try again."
                ),
                input_name=i.value,
                flow_input_keys=flow_input_keys,
            )
        return flow_inputs[i.value]
    if i.value_type == InputValueType.NODE_REFERENCE:
        if i.section != "output":
            raise UnsupportedReference(
                message_format=(
                    "Flow execution failed. "
                    "The section '{reference_section}' of reference is currently unsupported. "
                    "Please specify the output part of the node '{reference_node_name}'."
                ),
                reference_section=i.section,
                reference_node_name=i.value,
            )
        if i.value not in nodes_outputs:
            node_output_keys = [output_keys for output_keys in nodes_outputs.keys() if nodes_outputs]
            raise InputNotFoundFromAncestorNodeOutput(
                message_format=(
                    "Flow execution failed. "
                    "The input '{input_name}' is not found from ancestor node outputs {node_output_keys}. "
                    "Please check the node name and try again."
                ),
                input_name=i.value,
                node_output_keys=node_output_keys,
            )
        return parse_node_property(i.value, nodes_outputs[i.value], i.property)
    raise NotSupported(
        message_format=(
            "Flow execution failed. "
            "The type '{input_type}' is currently unsupported. "
            "Please choose from available types: {supported_output_type} and try again."
        ),
        input_type=i.value_type.value if hasattr(i.value_type, "value") else i.value_type,
        supported_output_type=[value_type.value for value_type in InputValueType],
    )


property_pattern = r"(\w+)|(\['.*?'\])|(\[\d+\])"


def parse_node_property(node_name, node_val, property=""):
    val = node_val
    property_parts = re.findall(property_pattern, property)
    try:
        for part in property_parts:
            part = [p for p in part if p][0]
            if part.startswith("[") and part.endswith("]"):
                index = part[1:-1]
                if index.startswith("'") and index.endswith("'") or index.startswith('"') and index.endswith('"'):
                    index = index[1:-1]
                elif index.isdigit():
                    index = int(index)
                else:
                    raise InvalidReferenceProperty(
                        message_format=(
                            "Flow execution failed. "
                            "Invalid index '{index}' when accessing property '{property}' of the node '{node_name}'. "
                            "Please check the index and try again."
                        ),
                        index=index,
                        property=property,
                        node_name=node_name,
                    )
                val = val[index]
            else:
                if isinstance(val, dict):
                    val = val[part]
                else:
                    val = getattr(val, part)
    except (KeyError, IndexError, AttributeError) as e:
        message_format = (
            "Flow execution failed. "
            "Invalid property '{property}' when accessing the node '{node_name}'. "
            "Please check the property and try again."
        )
        raise InvalidReferenceProperty(message_format=message_format, property=property, node_name=node_name) from e
    return val
