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
    @staticmethod
    def _ensure_nodes_order(flow: Flow):
        dependencies = {n.name: set() for n in flow.nodes}
        for n in flow.nodes:
            inputs_list = [i for i in n.inputs.values()]
            if n.skip:
                inputs_list.extend([n.skip.condition, n.skip.return_value])
            for i in inputs_list:
                if i.value_type != InputValueType.NODE_REFERENCE:
                    continue
                if i.value not in dependencies:
                    msg = (
                        f"Node '{n.name}' references a non-existent node '{i.value}' in your flow. "
                        f"Please review your flow YAML to ensure that the node name is accurately specified."
                    )
                    raise NodeReferenceNotFound(message=msg)
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
                    message=f"Node circular dependency has been detected among the nodes in your flow. "
                    f"Kindly review the reference relationships for the nodes {remaining_nodes} "
                    f"and resolve the circular reference issue in the flow YAML."
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
                    message=f"Node with name '{node.name}' appears more than once in the node definitions in your "
                    f"flow, which is not allowed. To address this issue, please review your "
                    f"flow YAML and either rename or remove nodes with identical names.",
                )
            node_names.add(node.name)
        for node in flow.nodes:
            for v in node.inputs.values():
                if v.value_type != InputValueType.FLOW_INPUT:
                    continue
                if v.value not in flow.inputs:
                    msg = (
                        f"Node '{node.name}' references flow input '{v.value}' which is not defined in your "
                        f"flow. To resolve this issue, please review your flow YAML, "
                        f"ensuring that you either add the missing flow inputs or adjust node reference "
                        f"to the correct flow input."
                    )
                    raise InputReferenceNotFound(message=msg)
        return FlowValidator._ensure_nodes_order(flow)

    @staticmethod
    def resolve_flow_inputs_type(flow: Flow, inputs: Mapping[str, Any], idx: Optional[int] = None) -> Mapping[str, Any]:
        """
        Resolve inputs by type if existing. Ignore missing inputs. This method is used for PRS case

        return:
            type converted inputs
        """
        updated_inputs = {k: v for k, v in inputs.items()}
        for k, v in flow.inputs.items():
            try:
                if k in inputs:
                    updated_inputs[k] = v.type.parse(inputs[k])
            except Exception as e:
                line_info = "" if idx is None else f"in line {idx} of input data"
                msg = (
                    f"The value '{inputs[k]}' for flow input '{k}' {line_info} does not match the expected type "
                    f"'{v.type}'. Please review the input data or adjust the input type of '{k}' in your flow."
                )
                raise InputTypeError(message=msg) from e
        return updated_inputs

    @staticmethod
    def ensure_flow_inputs_type(flow: Flow, inputs: Mapping[str, Any], idx: Optional[int] = None) -> Mapping[str, Any]:
        """
        Make sure the inputs are completed and in the correct type. Raise Exception if not valid.

        return:
            type converted inputs
        """
        for k, v in flow.inputs.items():
            if k not in inputs:
                line_info = "in input data" if idx is None else f"in line {idx} of input data"
                msg = (
                    f"The value for flow input '{k}' is not provided {line_info}. "
                    f"Please review your input data or remove this input in your flow if it's no longer needed."
                )
                raise InputNotFound(message=msg)
        return FlowValidator.resolve_flow_inputs_type(flow, inputs, idx)

    @staticmethod
    def convert_flow_inputs_for_node(flow: Flow, node: Node, inputs: Mapping[str, Any]):
        """
        Filter the flow inputs for node and resolve the value by type.

        return:
            the resolved flow inputs which are needed by the node only
        """
        updated_inputs = {}
        inputs = inputs or {}
        for k, v in node.inputs.items():
            if v.value_type == InputValueType.FLOW_INPUT:
                if v.value not in flow.inputs:
                    flow_input_keys = ", ".join(flow.inputs.keys()) if flow.inputs is not None else None
                    raise InputNotFound(
                        message=f"Node input {k} is not found in flow input '{flow_input_keys}' for node"
                    )
                if v.value not in inputs:
                    input_keys = ", ".join(inputs.keys())
                    raise InputNotFound(
                        message=f"Node input {k} is not found in input data with keys of '{input_keys}' for node"
                    )
                try:
                    updated_inputs[v.value] = flow.inputs[v.value].type.parse(inputs[v.value])
                except Exception as e:
                    msg = (
                        f"Input '{k}' for node '{node.name}' of value '{inputs[v.value]}' "
                        f"is not type '{flow.inputs[v.value].type}'."
                    )
                    raise InputTypeError(message=msg) from e
        return updated_inputs

    @staticmethod
    def _ensure_outputs_valid(flow: Flow):
        updated_outputs = {}
        for k, v in flow.outputs.items():
            if v.reference.value_type == InputValueType.LITERAL and v.reference.value == "":
                msg = (
                    f"The reference is not specified for the output '{k}' in the flow. "
                    f"To rectify this, ensure that you accurately specify the reference in the flow YAML."
                )
                raise EmptyOutputReference(message=msg)
            if v.reference.value_type == InputValueType.FLOW_INPUT and v.reference.value not in flow.inputs:
                msg = (
                    f"The output '{k}' references non-existent flow input '{v.reference.value}' in your flow. "
                    f"please carefully review your flow YAML "
                    f"and correct the reference definition for the output in question."
                )
                raise OutputReferenceNotFound(message=msg)
            if v.reference.value_type == InputValueType.NODE_REFERENCE:
                node = flow.get_node(v.reference.value)
                if node is None:
                    msg = (
                        f"The output '{k}' references non-existent node '{v.reference.value}' in your flow. "
                        f"To resolve this issue, please carefully review your flow YAML "
                        f"and correct the reference definition for the output in question."
                    )
                    raise OutputReferenceNotFound(message=msg)
                if node.aggregation:
                    msg = f"Output '{k}' references a reduce node '{v.reference.value}', will not take effect."
                    logger.warning(msg)
                    #  We will not add this output to the flow outputs, so we simply ignore it here
                    continue
            updated_outputs[k] = v
        return updated_outputs
