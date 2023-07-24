import copy
from typing import Any, Mapping, Optional

from promptflow.contracts.flow import Flow, InputAssignment, InputValueType, Node
from promptflow.contracts.tool import ConnectionType, Tool, ToolType, ValueType
from promptflow.core.connection_manager import ConnectionManager
from promptflow.core.tools_manager import BuiltinsManager
from promptflow.exceptions import ConnectionNotFound, ConnectionNotSet, ConnectionTypeUnresolved, ErrorTarget
from promptflow.executor.error_codes import (
    DuplicateNodeName,
    EmptyOutputError,
    InputNotFound,
    InputReferenceNotFound,
    InputTypeError,
    InvalidConnectionType,
    NodeCircularDependency,
    NodeInputValidationError,
    NodeReferenceNotFound,
    OutputReferenceNotFound,
    ToolNotFoundInFlow,
)
from promptflow.utils.logger_utils import logger


class FlowValidator:
    @staticmethod
    def resolve_llm_connection_to_input(tool: Tool, node: Node, connection_manager: ConnectionManager):
        """LLM connection is a separate field, the function will add it into node inputs."""
        results = {}
        if not node.connection:
            return results
        # 1. ensure connection provided is available in the connection manager.
        connection = connection_manager.get(node.connection)
        if connection is None:
            raise ConnectionNotFound(
                message=f"Connection {node.connection!r} not found, available connection keys "
                f"{connection_manager._connections.keys()}.",
                target=ErrorTarget.EXECUTOR,
            )
        # 2. Load provider/legacy tool, to check connection type is valid for the node.
        api_name = f"{node.provider}.{node.api}" if node.provider else None
        tool_func_name = f"{tool.class_name}.{tool.function}" if tool.class_name else None
        # a. Get provider api for llm tool
        # or b. Get new definition of legacy python tool, as the old one doesn't have connection input
        tool_def = BuiltinsManager.load_api_or_tool_by_name(api_name=api_name, tool_func_name=tool_func_name)
        # 3. Validate connection type: find the connection and get type class from inputs definition
        connection_type, key_name = None, None
        for key, input in tool_def.inputs.items():
            typ = input.type[0]
            connection_type = ConnectionType.get_connection_class(typ)
            key_name = key
            if connection_type:
                break
        if not connection_type:
            raise InvalidConnectionType(message=f"Connection type can not be resolved for tool {tool.name}")
        if type(connection).__name__ not in tool_def.inputs[key_name].type:
            msg = (
                f"Invalid connection '{node.connection}' type {type(connection).__name__!r} "
                f"for node '{node.name}', valid types {tool_def.inputs[key_name].type}."
            )
            raise InvalidConnectionType(message=msg)
        # 4. Add connection to node inputs if it's valid
        results[key_name] = InputAssignment(value=connection)
        return results

    @staticmethod
    def ensure_node_inputs_type(tool: Tool, node: Node, connections):
        # Create connection manager for connection dict
        # prerequisite modules will be imported here
        connection_manager = ConnectionManager(connections)
        #  Remove null values include empty string and null
        updated_inputs = {
            k: v
            for k, v in node.inputs.items()
            if (v.value is not None and v.value != "") or v.value_type != InputValueType.LITERAL
        }
        # LLM connection is a separate field, the function will add it into node inputs.
        # Note: Add this before load provider, because init provider class requires connection.
        connection_input = FlowValidator.resolve_llm_connection_to_input(tool, node, connection_manager)
        api_tool = None
        if BuiltinsManager.is_llm(tool):
            api_name = f"{node.provider}.{node.api}"
            # Get provider api for llm tool
            api_tool = BuiltinsManager.load_api_or_tool_by_name(api_name=api_name)
        for k, v in updated_inputs.items():
            if k not in tool.inputs and (not api_tool or api_tool and k not in api_tool.inputs):
                continue
            if v.value_type != InputValueType.LITERAL:
                continue
            tool_input = tool.inputs.get(k)
            if tool_input is None and api_tool:
                tool_input = api_tool.inputs.get(k)
            value_type = tool_input.type[0]
            updated_inputs[k] = copy.deepcopy(v)
            # v.value must in the connection manager.
            # if not, exception will be raised in 'resolve_llm_connection_to_input' before.
            connection_value = connection_manager.get(v.value)
            if connection_value:
                # value is a connection
                updated_inputs[k].value = connection_value
                # Check if type matched
                if not any(type(connection_value).__name__ == typ for typ in tool_input.type):
                    msg = (
                        f"Input '{k}' for node '{node.name}' of type {type(connection_value).__name__!r}"
                        f" is not supported, valid types {tool_input.type}."
                    )
                    raise NodeInputValidationError(message=msg)
            elif isinstance(value_type, ValueType):
                try:
                    updated_inputs[k].value = value_type.parse(v.value)
                except Exception as e:
                    msg = f"Input '{k}' for node '{node.name}' of value {v.value} is not type {value_type}."
                    raise NodeInputValidationError(message=msg) from e
            else:
                # The value type is in ValueType enum or is connection type. null connection has been handled before.
                raise ConnectionTypeUnresolved(
                    f"Unresolved input type {value_type!r}, please check if it is supported in current version.",
                    target=ErrorTarget.EXECUTOR,
                )
        updated_inputs.update(connection_input)
        updated_node = copy.copy(node)
        updated_node.inputs = updated_inputs
        return updated_node

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
        return flow

    @staticmethod  # noqa: C901
    def _ensure_nodes_valid(flow: Flow, connections):  # noqa: C901
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
                    msg = (
                        f"Node '{node.name}' references flow input '{v.value}' "
                        + f"which is not in the flow '{flow.name}'."
                    )
                    raise InputReferenceNotFound(message=msg)

        updated_nodes = []
        tools = {tool.name: tool for tool in flow.tools}
        for node in flow.nodes:
            if node.tool not in tools:
                msg = f"Node '{node.name}' references tool '{node.tool}' " + f"which is not in the flow '{flow.name}'."
                raise ToolNotFoundInFlow(message=msg)
            if tools[node.tool].type == ToolType.LLM and not node.api:
                msg = f"Please select connection for LLM node '{node.name}'."
                raise ConnectionNotSet(message=msg, target=ErrorTarget.EXECUTOR)
            updated_nodes.append(FlowValidator.ensure_node_inputs_type(tools[node.tool], node, connections))
        flow = copy.copy(flow)
        flow.nodes = updated_nodes
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
                msg = f"Input '{k}' in line {idx} for flow '{flow.name}' of value {inputs[k]} is not type {v.type}."
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
                raise InputNotFound(
                    message=f"Input '{k}' in line {idx} is not provided for flow '{flow.name}'.",
                )
        return FlowValidator.resolve_flow_inputs_type(flow, inputs, idx)

    @staticmethod
    def _ensure_outputs_valid(flow: Flow):
        updated_outputs = {}
        for k, v in flow.outputs.items():
            if v.reference.value_type == InputValueType.LITERAL and v.reference.value == "":
                msg = f"Output '{k}' is empty."
                raise EmptyOutputError(message=msg)
            if v.reference.value_type == InputValueType.FLOW_INPUT and v.reference.value not in flow.inputs:
                msg = (
                    f"Output '{k}' references flow input '{v.reference.value}' "
                    + f"which is not in the flow '{flow.name}'."
                )
                raise OutputReferenceNotFound(message=msg)
            if v.reference.value_type == InputValueType.NODE_REFERENCE:
                node = flow.get_node(v.reference.value)
                if node is None:
                    msg = f"Output '{k}' references node '{v.reference.value}' which is not in the flow '{flow.name}'."
                    raise OutputReferenceNotFound(message=msg)
                if node.reduce:
                    msg = f"Output '{k}' references a reduce node '{v.reference.value}', will not take effect."
                    logger.warning(msg)
                    #  We will not add this output to the flow outputs, so we simply ignore it here
                    continue
            updated_outputs[k] = v
        return updated_outputs

    @classmethod
    def ensure_flow_valid(cls, flow: Flow, connections: dict) -> Flow:
        flow = cls._ensure_nodes_valid(flow, connections)
        flow.outputs = cls._ensure_outputs_valid(flow)
        # TODO: Add more validations
        # TODO: Move to a separate validator class
        return flow
