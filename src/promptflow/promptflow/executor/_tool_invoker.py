# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import docutils.nodes
import os
from contextvars import ContextVar
from docutils.core import publish_doctree
from functools import partial
from pathlib import Path
from typing import Optional

from promptflow._core.thread_local_singleton import ThreadLocalSingleton
from promptflow._core.tool import ToolInvoker
from promptflow.contracts.flow import InputAssignment, Node, ToolSource
from promptflow.executor._tool_resolver import ToolResolver


class DefaultToolInvoker(ToolInvoker):
    def invoke_tool(self, f, *args, **kwargs):
        return f(*args, **kwargs)  # Do nothing


class AssistantToolInvoker(ToolInvoker):
    # CONTEXT_VAR_NAME = "Invoker"
    # context_var = ContextVar(CONTEXT_VAR_NAME, default=None)

    def __init__(self, connections: Optional[dict] = None):
        self._connections = connections
        self._resolved_tools = {}

    @classmethod
    def start_invoker(cls, connections: dict):
        invoker = cls(connections)
        cls.activate(invoker)

    @classmethod
    def load_tools(cls, tools: list):
        invoker = cls.active_instance()
        for tool in tools:
            if tool["type"] != "promptflow_tool":
                continue
            inputs = tool.get("inputs", {})
            updated_inputs = {}
            for input_name, value in inputs.items():
                updated_inputs[input_name] = InputAssignment.deserialize(value)
            node = Node(
                name="assistant_node",
                tool="assistant_tool",
                inputs=updated_inputs,
                source=ToolSource.deserialize(tool["source"])
            )
            tool_resolver = ToolResolver(working_dir=Path(os.getcwd()), connections=invoker._connections)
            resolved_tool = tool_resolver._resolve_script_node(node, convert_input_types=True)
            if resolved_tool.node.inputs:
                inputs = {name: value.value for name, value in resolved_tool.node.inputs.items()}
                callable = partial(resolved_tool.callable, **inputs)
                resolved_tool.callable = callable
            invoker._resolved_tools[resolved_tool.definition.function] = resolved_tool
        return invoker

    def to_openai_tools(self):
        openai_tools = []
        for func_name, resolved_tool in self._resolved_tools.items():
            preset_inputs = [name for name, _ in resolved_tool.node.inputs.items()]
            description = self._get_tool_description(func_name, resolved_tool.definition.description, preset_inputs)
            openai_tools.append(description)
        return openai_tools

    def invoke_tool(self, func_name, kwargs):
        return self._resolved_tools[func_name].callable(**kwargs)

    def _get_tool_description(self, func_name: str, docstring: str, preset_inputs: Optional[list] = None):
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
                params[param_name]["type"] = self._convert_type(field_body)

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

    def _convert_type(self, type: str):
        if type == "str":
            return "string"
        if type == "int":
            return "number"
