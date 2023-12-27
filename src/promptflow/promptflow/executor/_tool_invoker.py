# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import docutils.nodes
from dataclasses import dataclass
from docutils.core import publish_doctree
from functools import partial
from typing import Callable

from promptflow._core.tool import ToolInvoker
from promptflow.contracts.flow import InputAssignment, Node, ToolSource
from promptflow.executor._tool_resolver import ToolResolver


class DefaultToolInvoker(ToolInvoker):
    def invoke_tool(self, f, *args, **kwargs):
        return f(*args, **kwargs)  # Do nothing


@dataclass
class AssistantTool():
    name: str
    description: dict
    func: Callable


class AssistantToolInvoker():
    def __init__(self):
        self._assistant_tools = {}

    def load_tools(self, tools: list):
        tool_resolver = ToolResolver.active_instance()
        for tool in tools:
            if tool["type"] != "function":
                self._assistant_tools[tool["type"]] = AssistantTool(name=tool["type"], description=tool, func=None)
                continue
            inputs = tool.get("predefined_inputs", {})
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
            func_name = resolved_tool.definition.function
            description = self._get_function_description(func_name, resolved_tool.definition.description, inputs.keys())
            if resolved_tool.node.inputs:
                inputs = {name: value.value for name, value in resolved_tool.node.inputs.items()}
                func = partial(resolved_tool.callable, **inputs)
            else:
                func = resolved_tool.callable
            self._assistant_tools[func_name] = AssistantTool(name=func_name, description=description, func=func)

    def invoke_tool(self, func_name, kwargs):
        return self._assistant_tools[func_name].func(**kwargs)

    def to_openai_tools(self):
        return [tool.description for _, tool in self._assistant_tools.items()]

    def _get_function_description(self, func_name: str, description: str, predefined_inputs: list) -> dict:
        to_openai_type = {"str": "string", "int": "number"}

        doctree = publish_doctree(description)
        params = {}

        for field in doctree.traverse(docutils.nodes.field):
            field_name = field[0].astext()
            field_body = field[1].astext()

            if field_name.startswith("param"):
                param_name = field_name.split(' ')[1]
                if param_name in predefined_inputs:
                    continue
                if param_name not in params:
                    params[param_name] = {}
                params[param_name]["description"] = field_body
            if field_name.startswith("type"):
                param_name = field_name.split(' ')[1]
                if param_name in predefined_inputs:
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
