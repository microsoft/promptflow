# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import copy
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Callable, List, Optional

from promptflow._core.connection_manager import ConnectionManager
from promptflow._core.tools_manager import BuiltinsManager, CustomToolSourceLoadError, collect_package_tools
from promptflow._utils.generate_tool_meta_utils import (
    _parse_tool_from_function,
    collect_tool_function_in_module,
    load_python_module_from_file,
)
from promptflow._utils.tool_utils import get_prompt_param_name_from_func
from promptflow.contracts.flow import InputAssignment, InputValueType, Node, ToolSource, ToolSourceType
from promptflow.contracts.tool import ConnectionType, Tool, ToolType, ValueType
from promptflow.exceptions import ConnectionNotFound, ErrorTarget, UserErrorException, ValueTypeUnresolved
from promptflow.executor.error_codes import InvalidConnectionType, NodeInputValidationError


@dataclass
class ResolvedTool:
    node: Node
    definition: Tool
    callable: Callable
    init_args: dict


class ToolResolver:
    def __init__(self, working_dir: Path, connection_manager: Optional[ConnectionManager] = None):
        self._package_tools = collect_package_tools()
        self._working_dir = working_dir
        self._connection_manager = ConnectionManager() if connection_manager is None else connection_manager

    def _convert_to_connection_value(self, k: str, v: InputAssignment, node: Node, conn_types: List[ValueType]):
        connection_value = self._connection_manager.get(v.value)
        if not connection_value:
            raise ConnectionNotFound(f"Connection {v.value} not found for node {node.name!r} input {k!r}.")
        # Check if type matched
        if not any(type(connection_value).__name__ == typ for typ in conn_types):
            msg = (
                f"Input '{k}' for node '{node.name}' of type {type(connection_value).__name__!r}"
                f" is not supported, valid types {conn_types}."
            )
            raise NodeInputValidationError(message=msg)
        return connection_value

    def _convert_node_literal_input_types(self, node: Node, tool: Tool):
        updated_inputs = {
            k: v
            for k, v in node.inputs.items()
            if (v.value is not None and v.value != "") or v.value_type != InputValueType.LITERAL
        }
        for k, v in updated_inputs.items():
            if v.value_type != InputValueType.LITERAL:
                continue
            tool_input = tool.inputs.get(k)
            if tool_input is None:
                continue
            value_type = tool_input.type[0]
            updated_inputs[k] = InputAssignment(value=v.value, value_type=InputValueType.LITERAL)
            if ConnectionType.is_connection_class_name(value_type):
                updated_inputs[k].value = self._convert_to_connection_value(k, v, node, tool_input.type)
            elif isinstance(value_type, ValueType):
                try:
                    updated_inputs[k].value = value_type.parse(v.value)
                except Exception as e:
                    msg = f"Input '{k}' for node '{node.name}' of value {v.value} is not type {value_type}."
                    raise NodeInputValidationError(message=msg) from e
            else:
                # The value type is in ValueType enum or is connection type. null connection has been handled before.
                raise ValueTypeUnresolved(
                    f"Unresolved input type {value_type!r}, please check if it is supported in current version.",
                    target=ErrorTarget.EXECUTOR,
                )
        updated_node = copy.deepcopy(node)
        updated_node.inputs = updated_inputs
        return updated_node

    def resolve_tool_by_node(self, node: Node, convert_input_types=True) -> ResolvedTool:
        if node.source is None:
            raise UserErrorException(f"Node {node.name} does not have source defined.")

        if node.type is ToolType.PYTHON:
            if node.source.type == ToolSourceType.Package:
                return self._resolve_package_node(node, convert_input_types=convert_input_types)
            elif node.source.type == ToolSourceType.Code:
                return self._resolve_script_node(node, convert_input_types=convert_input_types)
            raise NotImplementedError(f"Tool source type {node.source.type} is not supported yet.")
        elif node.type is ToolType.PROMPT:
            return self._resolve_prompt_node(node)
        elif node.type is ToolType.LLM:
            return self._resolve_llm_node(node, convert_input_types=convert_input_types)
        else:
            raise NotImplementedError(f"Tool type {node.type} is not supported yet.")

    def _load_source_content(self, source: ToolSource) -> str:
        if source is None or source.path is None or not Path(self._working_dir / source.path).exists():
            raise UserErrorException(f"Node source path {source.path} is invalid.")
        with open(self._working_dir / source.path) as fin:
            return fin.read()

    def _resolve_prompt_node(self, node: Node) -> ResolvedTool:
        content = self._load_source_content(node.source)
        from promptflow.tools.template_rendering import render_template_jinja2

        callable = partial(render_template_jinja2, template=content)
        return ResolvedTool(node=node, definition=None, callable=callable, init_args={})

    @staticmethod
    def _remove_init_args(node_inputs: dict, init_args: dict):
        for k in init_args:
            if k in node_inputs:
                del node_inputs[k]

    def _resolve_llm_node(self, node: Node, convert_input_types=False) -> ResolvedTool:
        api_name = f"{node.provider}.{node.api}"
        tool: Tool = BuiltinsManager._load_llm_api(api_name)
        key, connection = self._resolve_llm_connection_to_inputs(node, tool)
        updated_node = copy.deepcopy(node)
        updated_node.inputs[key] = InputAssignment(value=connection, value_type=InputValueType.LITERAL)
        if convert_input_types:
            updated_node = self._convert_node_literal_input_types(updated_node, tool)

        prompt_tpl = self._load_source_content(node.source)
        api_func, init_args = BuiltinsManager._load_package_tool(
            tool.name, tool.module, tool.class_name, tool.function, updated_node.inputs
        )
        self._remove_init_args(updated_node.inputs, init_args)
        prompt_tpl_param_name = get_prompt_param_name_from_func(api_func)
        api_func = partial(api_func, **{prompt_tpl_param_name: prompt_tpl}) if prompt_tpl_param_name else api_func
        return ResolvedTool(updated_node, tool, api_func, init_args)

    def _resolve_llm_connection_to_inputs(self, node: Node, tool: Tool) -> Node:
        connection = self._connection_manager.get(node.connection)
        if connection is None:
            raise ConnectionNotFound(
                message=f"Connection {node.connection!r} not found, available connection keys "
                f"{self._connection_manager._connections.keys()}.",
                target=ErrorTarget.EXECUTOR,
            )
        for key, input in tool.inputs.items():
            if ConnectionType.is_connection_class_name(input.type[0]):
                if type(connection).__name__ not in input.type:
                    msg = (
                        f"Invalid connection '{node.connection}' type {type(connection).__name__!r} "
                        f"for node '{node.name}', valid types {input.type}."
                    )
                    raise InvalidConnectionType(message=msg)
                return key, connection
        raise InvalidConnectionType(
            message_format="Connection type can not be resolved for tool {tool_name}", tool_name=tool.name
        )

    def _resolve_script_node(self, node: Node, convert_input_types=False) -> ResolvedTool:
        if node.source.path is None:
            raise UserErrorException(f"Node {node.name} does not have source path defined.")
        path = node.source.path
        m = load_python_module_from_file(self._working_dir / path)
        if m is None:
            raise CustomToolSourceLoadError(f"Cannot load module from {path}.")
        f = collect_tool_function_in_module(m)
        tool = _parse_tool_from_function(f)
        if convert_input_types:
            node = self._convert_node_literal_input_types(node, tool)
        return ResolvedTool(node=node, definition=tool, callable=f, init_args={})

    def _resolve_package_node(self, node: Node, convert_input_types=False) -> ResolvedTool:
        tool = Tool.deserialize(self._package_tools[node.source.tool])
        updated_node = copy.deepcopy(node)
        if convert_input_types:
            updated_node = self._convert_node_literal_input_types(updated_node, tool)
        callable, init_args = BuiltinsManager._load_package_tool(
            tool.name, tool.module, tool.class_name, tool.function, updated_node.inputs
        )
        self._remove_init_args(updated_node.inputs, init_args)
        return ResolvedTool(node=updated_node, definition=tool, callable=callable, init_args=init_args)
