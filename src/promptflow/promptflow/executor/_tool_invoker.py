# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from functools import partial
from typing import Optional

import docutils.nodes
from docutils.core import publish_doctree

from promptflow._core.tool import ToolInvoker
from promptflow.contracts.flow import InputAssignment, Node, ToolSource
from promptflow.executor._tool_resolver import ToolResolver


class DefaultToolInvoker(ToolInvoker):
    def invoke_tool(self, f, *args, **kwargs):
        return f(*args, **kwargs)  # Do nothing


class AssistantToolInvoker:
    def __init__(self):
        self._assistant_tools = {}

    @classmethod
    def load_tools(cls, tools: list):
        invoker = AssistantToolInvoker()
        tool_resolver = ToolResolver.active_instance()
        for tool in tools:
            if tool["type"] != "promptflow_tool":
                continue
            inputs = tool.get("predefined_inputs", {})
            updated_inputs = {}
            for input_name, value in inputs.items():
                updated_inputs[input_name] = InputAssignment.deserialize(value)
            node = Node(
                name="assistant_node",
                tool="assistant_tool",
                inputs=updated_inputs,
                source=ToolSource.deserialize(tool["source"]),
            )
            resolved_tool = tool_resolver._resolve_script_node(node, convert_input_types=True)
            if resolved_tool.node.inputs:
                inputs = {name: value.value for name, value in resolved_tool.node.inputs.items()}
                callable = partial(resolved_tool.callable, **inputs)
                resolved_tool.callable = callable
            invoker._assistant_tools[resolved_tool.definition.function] = resolved_tool
        return invoker

    def invoke_tool(self, func_name, kwargs):
        return self._assistant_tools[func_name].callable(**kwargs)

    def to_openai_tools(self):
        openai_tools = []
        for _, tool in self._assistant_tools.items():
            description = tool.definition.structured_description
            preset_inputs = [name for name, _ in tool.node.inputs.items()]
            # description = self._get_openai_tool_description(name, tool.definition.description, preset_inputs)
            if preset_inputs:
                description = self._remove_predefined_inputs(description, preset_inputs)
            openai_tools.append(tool.definition.structured_description)
        return openai_tools

    def _remove_predefined_inputs(self, description: dict, preset_inputs: Optional[list] = None):
        param_names = description["function"]["parameters"]["required"]
        params = description["function"]["parameters"]["properties"]
        for input_name in preset_inputs:
            param_names.remove(input_name)
            params.pop(input_name)
        return description

    def _get_openai_tool_description(self, func_name: str, docstring: str, preset_inputs: Optional[list] = None):
        to_openai_type = {"str": "string", "int": "number", "float": "number", "bool": "boolean"}

        doctree = publish_doctree(docstring)
        params = {}

        for field in doctree.traverse(docutils.nodes.field):
            field_name = field[0].astext()
            field_body = field[1].astext()

            if field_name.startswith("param"):
                param_name = field_name.split(" ")[1]
                if param_name in preset_inputs:
                    continue
                if param_name not in params:
                    params[param_name] = {}
                params[param_name]["description"] = field_body
            if field_name.startswith("type"):
                param_name = field_name.split(" ")[1]
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
                "parameters": {"type": "object", "properties": params, "required": list(params.keys())},
            },
        }
