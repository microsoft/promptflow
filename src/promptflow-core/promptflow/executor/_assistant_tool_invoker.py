from dataclasses import dataclass
from typing import Callable, Dict, Optional

from promptflow.contracts.flow import ToolSource, ToolSourceType
from promptflow.contracts.tool import ToolType, ValueType
from promptflow.exceptions import ErrorTarget
from promptflow.executor._errors import InvalidAssistantTool

to_json_type_mapping = {
    ValueType.INT: "number",
    ValueType.DOUBLE: "number",
    ValueType.BOOL: "boolean",
    ValueType.STRING: "string",
    ValueType.LIST: "array",
    ValueType.OBJECT: "object",
}


@dataclass
class AssistantTool:
    """Assistant tool definition.

    This is internal contract for tool resolving.
    """

    type: str  # Openai assistant tool type ['function', 'retrieval', 'code_interpreter']
    tool_type: ToolType  # promptflow tool type
    source: ToolSource  # Tool sourcing definition
    predefined_inputs: Optional[Dict[str, str]] = None  # Predefined inputs for the tool, optional


class AssistantToolResolver:
    @classmethod
    def from_dict(cls, data: dict, node_name: str = None) -> AssistantTool:

        type = data.get("type", None)
        if type not in ["code_interpreter", "function", "retrieval"]:
            raise InvalidAssistantTool(
                message_format=(
                    "Unsupported assistant tool's type in node {node_name} : {type}. "
                    "Please make sure the type is restricted within "
                    "['code_interpreter', 'function', 'retrieval']."
                ),
                type=type,
                target=ErrorTarget.EXECUTOR,
            )

        try:
            tool_type = ToolType(data.get("tool_type"))
        except ValueError:
            raise InvalidAssistantTool(
                message_format=(
                    "The 'tool_type' property is missing or invalid in assistant node '{node_name}'. "
                    "Please make sure the assistant definition is correct."
                ),
                node_name=node_name,
                target=ErrorTarget.EXECUTOR,
            )

        if tool_type not in [ToolType.PYTHON]:
            raise InvalidAssistantTool(
                message_format=(
                    "Tool type '{tool_type}' is not supported in assistant node '{node_name}'. "
                    "Please make sure the assistant definition is correct."
                ),
                tool_type=tool_type.value,
                node_name=node_name,
                target=ErrorTarget.EXECUTOR,
            )

        if "source" not in data:
            raise InvalidAssistantTool(
                message_format=(
                    "The 'source' property is missing in the assistant node '{node_name}'. "
                    "Please make sure the assistant definition is correct."
                ),
                node_name=node_name,
                target=ErrorTarget.EXECUTOR,
            )

        try:
            tool_source = ToolSource.deserialize(data.get("source"))
        except ValueError:
            raise InvalidAssistantTool(
                message_format=(
                    "The 'source' definition is not valid in the assistant node '{node_name}'. "
                    "Please make sure the assistant definition is correct and deserializable."
                ),
                node_name=node_name,
                target=ErrorTarget.EXECUTOR,
            )

        if tool_source.type == ToolSourceType.Package:
            if not tool_source.tool:
                raise InvalidAssistantTool(
                    message_format=(
                        "The 'tool' property is missing in 'source' of the assistant package tool "
                        "in node '{node_name}'. Please make sure the assistant definition is correct."
                    ),
                    node_name=node_name,
                    target=ErrorTarget.EXECUTOR,
                )
        elif tool_source.type == ToolSourceType.Code:
            if not tool_source.path:
                raise InvalidAssistantTool(
                    message_format=(
                        "The 'path' property is missing in 'source' of the assistant python tool "
                        "in node '{node_name}'. Please make sure the assistant definition is correct."
                    ),
                    node_name=node_name,
                    target=ErrorTarget.EXECUTOR,
                )

        else:
            raise InvalidAssistantTool(
                message_format=(
                    "Tool source type '{source_type}' is not supported in assistant node '{node_name}'. "
                    "Please make sure the assistant definition is correct."
                ),
                node_name=node_name,
                source_type=tool_source.type,
                target=ErrorTarget.EXECUTOR,
            )

        return AssistantTool(
            type=type,
            tool_type=tool_type,
            source=tool_source,
            predefined_inputs=data.get("predefined_inputs", None),
        )


@dataclass
class ResolvedAssistantTool:
    """Resolved assistant tool structure.

    The contract is used to stored resolved assistant tool, including
    connection,
    openai tool json definition,
    callable function, etc
    """

    name: str
    openai_definition: dict
    func: Callable


class AssistantToolInvoker:
    def __init__(self, tools: Dict[str, ResolvedAssistantTool]):
        self._assistant_tools = tools

    def invoke_tool(self, func_name, kwargs):
        return self._assistant_tools[func_name].func(**kwargs)

    def to_openai_tools(self):
        return [tool.openai_definition for tool in self._assistant_tools.values()]
