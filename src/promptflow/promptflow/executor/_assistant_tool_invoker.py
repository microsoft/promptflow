from dataclasses import dataclass
from typing import Callable, Dict, Optional

from promptflow.contracts.flow import ToolSource


@dataclass
class AssistantTool:
    """Assistant tool definition.

    This is internal contract for tool resolving.
    """

    type: str  # Openai assistant tool type ['function', 'retrieval', 'code_interpreter']
    tool_type: str  # promptflow tool type
    source: Optional[ToolSource]  # Tool sourcing definition
    predefined_inputs: Optional[Dict[str, str]] = None

    @classmethod
    def from_dict(cls, data: dict):
        tool_source = None
        if "source" in data:
            tool_source = ToolSource.deserialize(data["source"])

        return cls(
            type=data.get("type", None),
            tool_type=data.get("tool_type", None),
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
