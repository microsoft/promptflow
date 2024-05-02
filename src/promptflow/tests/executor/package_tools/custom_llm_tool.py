from jinja2 import Template

from promptflow.connections import AzureOpenAIConnection
from promptflow.contracts.types import PromptTemplate
from promptflow.core import ToolProvider, tool


class TestCustomLLMTool(ToolProvider):
    def __init__(self, connection: AzureOpenAIConnection):
        super().__init__()
        self.connection = connection

    @tool
    def call(self, connection_2: AzureOpenAIConnection, api: str, template: PromptTemplate, **kwargs):
        prompt = Template(template, trim_blocks=True, keep_trailing_newline=True).render(**kwargs)
        assert isinstance(self.connection, AzureOpenAIConnection)
        assert isinstance(connection_2, AzureOpenAIConnection)
        assert api in ["completion", "chat"]
        return prompt
