from typing import Dict

from promptflow.contracts.types import AssistantDefinition, AssistantTool


class AssistantToolInvoker:
    def __init__(self, tools: Dict[str, AssistantTool]):
        self._assistant_tools = tools

    @classmethod
    def init(cls, assistant_definition: AssistantDefinition):
        invoker = cls(tools=assistant_definition.assistant_tools)
        return invoker

    def invoke_tool(self, func_name, kwargs):
        return self._assistant_tools[func_name].func(**kwargs)

    def to_openai_tools(self):
        return [tool.openai_definition for tool in self._assistant_tools.values()]
