# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import re

from promptflow.contracts.flow import InputAssignment, InputValueType
from promptflow.executor._errors import (
    InputNotFound,
    InputNotFoundFromAncestorNodeOutput,
    InvalidReferenceProperty,
    UnsupportedReference,
)


def is_node_dependency_skipped(dependency: InputAssignment, skipped_nodes: dict, completed_node_outputs: dict) -> bool:
    """Returns True if the dependencies of the condition are skipped."""
    # The node should not be skipped when its dependency is skipped by skip config and the dependency has outputs.
    return dependency.value_type == InputValueType.NODE_REFERENCE and \
        dependency.value in skipped_nodes and \
        dependency.value not in completed_node_outputs


def parse_value(i: InputAssignment, nodes_outputs: dict, flow_inputs: dict):
    if i.value_type == InputValueType.LITERAL:
        return i.value
    if i.value_type == InputValueType.FLOW_INPUT:
        if i.value not in flow_inputs:
            flow_input_keys = ", ".join(flow_inputs.keys()) if flow_inputs is not None else None
            raise InputNotFound(message=f"{i.value} is not found from flow inputs '{flow_input_keys}'")
        return flow_inputs[i.value]
    if i.value_type == InputValueType.NODE_REFERENCE:
        if i.section != "output":
            raise UnsupportedReference(f"Unsupported reference {i.serialize()}")
        if i.value not in nodes_outputs:
            node_output_keys = ", ".join(nodes_outputs.keys()) if nodes_outputs is not None else None
            raise InputNotFoundFromAncestorNodeOutput(
                message=f"{i.value} is not found from ancestor node output '{node_output_keys}'"
            )
        return parse_node_property(i.value, nodes_outputs[i.value], i.property)
    raise NotImplementedError(f"The value type {i.value_type} cannot be parsed for input {i}")


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
                    raise InvalidReferenceProperty(f"Invalid index {index} when accessing property {property}")
                val = val[index]
            else:
                if isinstance(val, dict):
                    val = val[part]
                else:
                    val = getattr(val, part)
    except (KeyError, IndexError, AttributeError) as e:
        raise InvalidReferenceProperty(f"Invalid property {property} for the node {node_name}") from e
    return val
