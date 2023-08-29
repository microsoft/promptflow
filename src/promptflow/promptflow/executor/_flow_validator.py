# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import copy
from typing import Any, Mapping, Optional

from promptflow._utils.logger_utils import logger
from promptflow.contracts.flow import Flow, InputValueType, Node
from promptflow.executor._errors import (
    DuplicateNodeName,
    EmptyOutputError,
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
                    msg = f"Node '{n.name}' references node '{i.value}' which is not in the flow '{flow.name}'."
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
                raise NodeCircularDependency(message=f"There is a circular dependency in the flow '{flow.name}'.")
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
                    message=f"Node name '{node.name}' is duplicated in the flow '{flow.name}'.",
                )
            node_names.add(node.name)
        for node in flow.nodes:
            for v in node.inputs.values():
                if v.value_type != InputValueType.FLOW_INPUT:
                    continue
                if v.value not in flow.inputs:
                    msg = f"Node '{node.name}' references flow input '{v.value}' which is not in the flow."
                    raise InputReferenceNotFound(message=msg)
        return FlowValidator._ensure_nodes_order(flow)

    @staticmethod
    def _resolve_flow_inputs_type(flow: Flow, inputs: Mapping[str, Any], idx: Optional[int] = None) -> Mapping[str, Any]:
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
                msg = f"Input '{k}' in line {idx} for flow '{flow.name}' of value {inputs[k]} is not type {v.type}."
                raise InputTypeError(message=msg) from e
        return updated_inputs

    @staticmethod
    def _ensure_flow_inputs_type(flow: Flow, inputs: Mapping[str, Any], idx: Optional[int] = None) -> Mapping[str, Any]:
        """
        Make sure the inputs are completed and in the correct type. Raise Exception if not valid.

        return:
            type converted inputs
        """
        for k, v in flow.inputs.items():
            if k not in inputs:
                message = f"Input '{k}'" if idx is None else f"Input '{k}' in line {idx}"
                raise InputNotFound(message=f"{message} is not provided for flow.")
        return FlowValidator._resolve_flow_inputs_type(flow, inputs, idx)

    @staticmethod
    def _convert_flow_inputs_for_node(flow: Flow, node: Node, inputs: Mapping[str, Any]):
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
                msg = f"Output '{k}' is empty."
                raise EmptyOutputError(message=msg)
            if v.reference.value_type == InputValueType.FLOW_INPUT and v.reference.value not in flow.inputs:
                msg = f"Output '{k}' references flow input '{v.reference.value}' which is not in the flow."
                raise OutputReferenceNotFound(message=msg)
            if v.reference.value_type == InputValueType.NODE_REFERENCE:
                node = flow.get_node(v.reference.value)
                if node is None:
                    msg = f"Output '{k}' references node '{v.reference.value}' which is not in the flow '{flow.name}'."
                    raise OutputReferenceNotFound(message=msg)
                if node.aggregation:
                    msg = f"Output '{k}' references a reduce node '{v.reference.value}', will not take effect."
                    logger.warning(msg)
                    #  We will not add this output to the flow outputs, so we simply ignore it here
                    continue
            updated_outputs[k] = v
        return updated_outputs
