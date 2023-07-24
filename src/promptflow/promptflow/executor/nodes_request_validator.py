from typing import Dict

from promptflow.contracts.flow import Flow, FlowInputAssignment, FlowInputDefinition, InputValueType, Node, NodesRequest
from promptflow.exceptions import ErrorTarget, ValidationException
from promptflow.executor.flow_validator import FlowValidator


class NodesRequestValidator:
    @staticmethod
    def ensure_single_node(flow: Flow, node_name: str, connections: dict):
        # node_name must match one node.
        target_node = [n for n in flow.nodes if n.name == node_name]
        if len(target_node) == 0:
            raise NodeNotFoundByName(
                message=f"No node with name {node_name}.",
            )
        target_node = target_node[0]

        # Single node must not be reduce node.
        if target_node.reduce:
            raise SingleNodeModeNotSupportedForReduce(
                message="Aggregation node does not support single node run.",
            )

        # Ensure tool exists.
        name_to_tool = {tool.name: tool for tool in flow.tools}
        tool = name_to_tool.get(target_node.tool)
        if tool is None:
            raise ToolNotFoundInFlow(
                message=f"Node '{target_node.name}' references tool '{target_node.tool}' "
                + f"which is not in the flow '{flow.name}'.",  # noqa: W504
            )

        # Ensure node's inputs type.
        updated_node = FlowValidator.ensure_node_inputs_type(tool, target_node, connections)

        return updated_node

    @staticmethod
    def ensure_single_node_inputs(flow: Flow, node: Node, node_inputs: Dict):
        # All reference node' input must be in node_inputs
        node_inputs_keys = set(NodesRequest.get_node_name_from_node_inputs_key(k) for k in node_inputs)
        missing_inputs = list()
        for _, input in node.inputs.items():
            if input.value_type == InputValueType.FLOW_INPUT:
                input_value = input.prefix + input.value
                if input_value not in node_inputs_keys:
                    missing_inputs.append(input_value)
            elif input.value_type == InputValueType.NODE_REFERENCE:
                if input.value not in node_inputs_keys:
                    missing_inputs.append(input.value)

        if len(missing_inputs) > 0:
            raise EmptyInputError(
                message=f"Missing node inputs: {', '.join(missing_inputs)}",
            )

        # Convert node_inputs to target type
        updated_inputs = {k: v for k, v in node_inputs.items()}
        for k, v in node_inputs.items():
            if FlowInputAssignment.is_flow_input(k):
                k_without_prefix = FlowInputAssignment.deserialize(k).value
                if k_without_prefix not in flow.inputs:
                    raise InputNotFound(
                        message=f"Node input '{k}' is not in flow inputs. '{flow.name}'.",
                    )

                v: FlowInputDefinition = flow.inputs[k_without_prefix]
                try:
                    updated_inputs[k] = v.type.parse(node_inputs[k])
                except Exception as e:
                    msg = f"Input '{k}' in node input of value {node_inputs[k]} is not type {v.type}."
                    raise InputConvertTypeError(message=msg) from e

        return updated_inputs


class InvalidNodeRequest(ValidationException):
    def __init__(
        self,
        target: ErrorTarget = ErrorTarget.EXECUTOR,
        **kwargs,
    ):
        super().__init__(
            target=target,
            **kwargs,
        )


class NodeNotFoundByName(InvalidNodeRequest):
    pass


class SingleNodeModeNotSupportedForReduce(InvalidNodeRequest):
    pass


class ToolNotFoundInFlow(InvalidNodeRequest):
    pass


class EmptyInputError(InvalidNodeRequest):
    pass


class InputNotFound(InvalidNodeRequest):
    pass


class InputConvertTypeError(InvalidNodeRequest):
    pass
