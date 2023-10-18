from promptflow import ToolProvider, tool
from promptflow.connections import AzureOpenAIConnection
from promptflow.contracts.types import PromptTemplate


class TestCustomLLMTool(ToolProvider):
    def __init__(self, connection: AzureOpenAIConnection):
        super().__init__()
        self.connection = connection

    @tool(name="custom_llm_tool", type="custom_llm")
    def tool_func(self, api: str, template: PromptTemplate, **kwargs):
        pass
