from jinja2 import Template
from promptflow.connections import CustomConnection

from promptflow.core import ToolProvider, tool
from promptflow.connections import AzureOpenAIConnection
from promptflow.contracts.types import PromptTemplate


class TestCustomLLMTool(ToolProvider):
    def __init__(self, connection: AzureOpenAIConnection):
        super().__init__()
        self.connection = connection

    @tool(
        name="My Custom LLM Tool",
        type="custom_llm",
        description="This is a tool to demonstrate the custom_llm tool type",
    )
    def tool_func(self, api: str, template: PromptTemplate, **kwargs):
        pass


@tool(
    name="My Custom LLM Tool",
    type="custom_llm",
    description="This is a tool to demonstrate the custom_llm tool type",
)
def my_tool(connection: CustomConnection, prompt: PromptTemplate, **kwargs) -> str:
    # Replace with your tool code, customise your own code to handle and use the prompt here.
    # Usually connection contains configs to connect to an API.
    # Not all tools need a connection. You can remove it if you don't need it.
    rendered_prompt = Template(prompt, trim_blocks=True, keep_trailing_newline=True).render(**kwargs)
    return rendered_prompt
