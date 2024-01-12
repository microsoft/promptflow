from jinja2 import Template
from promptflow import tool
from promptflow.connections import CustomConnection
from promptflow.contracts.types import PromptTemplate


@tool
def my_tool(connection: CustomConnection, prompt: PromptTemplate, **kwargs) -> str:
    # Replace with your tool code, customise your own code to handle and use the prompt here.
    # Usually connection contains configs to connect to an API.
    # Not all tools need a connection. You can remove it if you don't need it.
    rendered_prompt = Template(prompt, trim_blocks=True, keep_trailing_newline=True).render(**kwargs)
    return rendered_prompt
