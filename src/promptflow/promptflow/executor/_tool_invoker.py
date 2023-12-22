# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import docutils.nodes
from docutils.core import publish_doctree
from contextvars import ContextVar
from functools import partial
from typing import List, Optional

from promptflow.contracts.flow import InputAssignment, Node, ToolSource
from promptflow.executor._tool_resolver import ToolResolver


class DefaultToolInvoker():
    CONTEXT_VAR_NAME = "Invoker"
    context_var = ContextVar(CONTEXT_VAR_NAME, default=None)

    def __init__(self):
        self._tools = {}
        self._assistant_tools = {}

    @property
    def tools(self):
        return self._tools

    # @classmethod
    # def start_invoker(cls):
    #     invoker = cls()
    #     active_invoker = cls.active_instance()
    #     if active_invoker:
    #         active_invoker._deactivate_in_context()
    #     cls._activate_in_context(invoker)
    #     return invoker

    @classmethod
    def load_tools(self, nodes: List[Node]):
        invoker = DefaultToolInvoker()
        tool_resolver = ToolResolver.active_instance()
        invoker._tools = {node.name: tool_resolver.resolve_tool_by_node(node) for node in nodes}
        return invoker

    @classmethod
    def load_assistant_tools(cls, tools: list):
        invoker = DefaultToolInvoker()
        tool_resolver = ToolResolver.active_instance()
        for tool in tools:
            if tool["type"] != "promptflow_tool":
                continue
            inputs = tool.get("pre_assigned_inputs", {})
            updated_inputs = {}
            for input_name, value in inputs.items():
                updated_inputs[input_name] = InputAssignment.deserialize(value)
            node = Node(
                name="assistant_node",
                tool="assistant_tool",
                inputs=updated_inputs,
                source=ToolSource.deserialize(tool["source"])
            )
            resolved_tool = tool_resolver._resolve_script_node(node, convert_input_types=True)
            if resolved_tool.node.inputs:
                inputs = {name: value.value for name, value in resolved_tool.node.inputs.items()}
                callable = partial(resolved_tool.callable, **inputs)
                resolved_tool.callable = callable
            invoker._assistant_tools[resolved_tool.definition.function] = resolved_tool
        return invoker

    def invoke_assistant_tool(self, func_name, kwargs):
        return self._assistant_tools[func_name].callable(**kwargs)

    def to_openai_tools(self):
        openai_tools = []
        for name, tool in self._assistant_tools.items():
            preset_inputs = [name for name, _ in tool.node.inputs.items()]
            description = self._get_openai_tool_description(name, tool.definition.description, preset_inputs)
            openai_tools.append(description)
        return openai_tools

    def _get_openai_tool_description(self, func_name: str, docstring: str, preset_inputs: Optional[list] = None):
        to_openai_type = {"str": "string", "int": "number"}

        doctree = publish_doctree(docstring)
        params = {}

        for field in doctree.traverse(docutils.nodes.field):
            field_name = field[0].astext()
            field_body = field[1].astext()

            if field_name.startswith("param"):
                param_name = field_name.split(' ')[1]
                if param_name in preset_inputs:
                    continue
                if param_name not in params:
                    params[param_name] = {}
                params[param_name]["description"] = field_body
            if field_name.startswith("type"):
                param_name = field_name.split(' ')[1]
                if param_name in preset_inputs:
                    continue
                if param_name not in params:
                    params[param_name] = {}
                params[param_name]["type"] = to_openai_type[field_body] if field_body in to_openai_type else field_body

        return {
            "type": "function",
            "function": {
                "name": func_name,
                "description": doctree[0].astext(),
                "parameters": {
                    "type": "object",
                    "properties": params,
                    "required": list(params.keys())
                }
            }
        }
