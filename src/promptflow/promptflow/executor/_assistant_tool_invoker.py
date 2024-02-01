import os
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Callable, Dict, Optional

from promptflow.contracts.flow import InputAssignment, Node, ToolSource
from promptflow.contracts.tool import ToolType
from promptflow.exceptions import ErrorTarget
from promptflow.executor._docstring_parser import DocstringParser
from promptflow.executor._errors import UnsupportedAssistantToolType
from promptflow.executor._tool_resolver import ToolResolver


@dataclass
class AssistantTool:
    name: str
    openai_definition: dict
    func: Callable


class AssistantToolInvoker:
    def __init__(self, working_dir: Optional[Path] = None):
        self._working_dir = working_dir or Path(os.getcwd())
        self._assistant_tools: Dict[str, AssistantTool] = {}

    @classmethod
    def init(cls, tools: list, working_dir: Optional[Path] = None):
        invoker = cls(working_dir=working_dir)
        invoker._load_tools(tools)
        return invoker

    def _load_tools(self, tools: list):
        for tool in tools:
            if tool["type"] in ("code_interpreter", "retrieval"):
                self._assistant_tools[tool["type"]] = AssistantTool(
                    name=tool["type"], openai_definition=tool, func=None
                )
            elif tool["type"] == "function":
                function_tool = self._load_tool_as_function(tool)
                self._assistant_tools[function_tool.name] = function_tool
            else:
                raise UnsupportedAssistantToolType(
                    message_format="Unsupported assistant tool type: {tool_type}",
                    tool_type=tool["type"],
                    target=ErrorTarget.EXECUTOR,
                )

    def _load_tool_as_function(self, tool: dict):
        tool_resolver = ToolResolver(self._working_dir)
        node, predefined_inputs = self._generate_node_for_tool(tool)
        resolved_tool = tool_resolver.resolve_tool_by_node(node, convert_input_types=False)
        func_name = resolved_tool.definition.function
        definition = self._generate_tool_definition(func_name, resolved_tool.definition.description, predefined_inputs)
        if resolved_tool.node.inputs:
            inputs = {name: value.value for name, value in resolved_tool.node.inputs.items()}
            func = partial(resolved_tool.callable, **inputs)
        else:
            func = resolved_tool.callable
        return AssistantTool(name=func_name, openai_definition=definition, func=func)

    def _generate_node_for_tool(self, tool: dict):
        predefined_inputs = {}
        for input_name, value in tool.get("predefined_inputs", {}).items():
            predefined_inputs[input_name] = InputAssignment.deserialize(value)
        node = Node(
            name="assistant_node",
            tool="assistant_tool",
            inputs=predefined_inputs,
            source=ToolSource.deserialize(tool["source"]) if "source" in tool else None,
            type=ToolType.PYTHON if "tool_type" in tool and tool["tool_type"] == "python" else None,
        )
        return node, list(predefined_inputs.keys())

    def invoke_tool(self, func_name, kwargs):
        return self._assistant_tools[func_name].func(**kwargs)

    def to_openai_tools(self):
        return [tool.openai_definition for tool in self._assistant_tools.values()]

    def _generate_tool_definition(self, func_name: str, description: str, predefined_inputs: list) -> dict:
        to_openai_type = {
            "str": "string",
            "int": "number",
            "float": "number",
            "bool": "boolean",
            "list": "array",
            "dict": "object",
        }
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
                "parameters": {"type": "object", "properties": params, "required": list(params.keys())},
            },
        }
