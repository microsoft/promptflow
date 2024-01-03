# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from dataclasses import dataclass
from functools import partial
from typing import Callable, Dict

from promptflow._core.tool import ToolInvoker
from promptflow.contracts.flow import InputAssignment, Node, ToolSource
from promptflow.exceptions import ErrorTarget
from promptflow.executor._docstring_parser import DocstringParser
from promptflow.executor._errors import UnsupportedAssistantToolType
from promptflow.executor._tool_resolver import ToolResolver


class DefaultToolInvoker(ToolInvoker):
    def invoke_tool(self, f, *args, **kwargs):
        return f(*args, **kwargs)  # Do nothing


@dataclass
class AssistantTool:
    name: str
    definition: dict
    func: Callable


class AssistantToolInvoker:
    def __init__(self):
        self._assistant_tools: Dict[str, AssistantTool] = {}

    def load_tools(self, tools: list):
        for tool in tools:
            if tool["type"] in ("code_interpreter", "retrieval"):
                self._assistant_tools[tool["type"]] = AssistantTool(name=tool["type"], definition=tool, func=None)
            elif tool["type"] == "function":
                function_tool = self._load_function_tool(tool)
                self._assistant_tools[function_tool.name] = function_tool
            else:
                raise UnsupportedAssistantToolType(
                    message_format="Unsupported assistant tool type: {tool_type}",
                    tool_type=tool["type"],
                    target=ErrorTarget.EXECUTOR,
                )

    def _load_function_tool(self, tool: dict):
        tool_resolver = ToolResolver.active_instance()
        predefined_inputs = {}
        for input_name, value in tool.get("predefined_inputs", {}).items():
            predefined_inputs[input_name] = InputAssignment.deserialize(value)
        node = Node(
            name="assistant_node",
            tool="assistant_tool",
            inputs=predefined_inputs,
            source=ToolSource.deserialize(tool["source"])
        )
        resolved_tool = tool_resolver._resolve_script_node(node, convert_input_types=True)
        func_name = resolved_tool.definition.function
        definition = self._generate_tool_definition(
            func_name, resolved_tool.definition.description, predefined_inputs.keys()
        )
        if resolved_tool.node.inputs:
            inputs = {name: value.value for name, value in resolved_tool.node.inputs.items()}
            func = partial(resolved_tool.callable, **inputs)
        else:
            func = resolved_tool.callable
        return AssistantTool(name=func_name, definition=definition, func=func)

    def invoke_tool(self, func_name, kwargs):
        return self._assistant_tools[func_name].func(**kwargs)

    def to_openai_tools(self):
        return [tool.definition for _, tool in self._assistant_tools.items()]

    def _generate_tool_definition(self, func_name: str, description: str, predefined_inputs: list) -> dict:
        to_openai_type = {"str": "string", "int": "number"}
        description, params = DocstringParser.parse(description)
        for input in predefined_inputs:
            if input in params:
                params.pop(input)
        for _, param in params.items():
            param["type"] = to_openai_type[param["type"]] if param["type"] in to_openai_type else param["type"]

        return {
            "type": "function",
            "function": {
                "name": func_name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": params,
                    "required": list(params.keys())
                }
            }
        }
