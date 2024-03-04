from dataclasses import dataclass
from typing import Callable, Dict


@dataclass
class AssistantTool:
    name: str
    openai_definition: dict
    func: Callable


class AssistantToolInvoker:
    def __init__(self, tools: Dict[str, AssistantTool]):
        self._assistant_tools = tools

    def invoke_tool(self, func_name, kwargs):
        return self._assistant_tools[func_name].func(**kwargs)

    def to_openai_tools(self):
        return [tool.openai_definition for tool in self._assistant_tools.values()]
