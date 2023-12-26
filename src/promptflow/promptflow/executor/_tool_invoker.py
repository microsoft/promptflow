# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from functools import partial
from typing import Optional

from promptflow._core.tool import ToolInvoker
from promptflow.contracts.flow import InputAssignment, Node, ToolSource
from promptflow.executor._tool_resolver import ToolResolver


class DefaultToolInvoker(ToolInvoker):
    def invoke_tool(self, f, *args, **kwargs):
        return f(*args, **kwargs)  # Do nothing


class AssistantToolInvoker():
    def __init__(self):
        self._assistant_tools = {}

    def load_tools(self, tools: list):
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
                source=ToolSource.deserialize(tool["source"])
            )
            resolved_tool = tool_resolver._resolve_script_node(node, convert_input_types=True)
            if resolved_tool.node.inputs:
                inputs = {name: value.value for name, value in resolved_tool.node.inputs.items()}
                callable = partial(resolved_tool.callable, **inputs)
                resolved_tool.callable = callable
            self._assistant_tools[resolved_tool.definition.function] = resolved_tool

    def invoke_tool(self, func_name, kwargs):
        return self._assistant_tools[func_name].callable(**kwargs)

    def to_openai_tools(self):
        openai_tools = []
        for _, tool in self._assistant_tools.items():
            description = tool.definition.structured_description
            preset_inputs = [name for name, _ in tool.node.inputs.items()]
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
