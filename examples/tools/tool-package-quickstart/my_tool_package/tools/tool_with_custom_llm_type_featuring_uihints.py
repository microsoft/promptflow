from jinja2 import Template
from promptflow import tool
from promptflow.connections import CustomConnection
from promptflow.contracts.types import PromptTemplate
from promptflow.entities import InputSetting


input_settings = {
    "connection": InputSetting(ui_hints={"text_box_size": "lg"}),
    "endpoint_name": InputSetting(ui_hints={"text_box_size": "md"}),
    "api": InputSetting(ui_hints={"text_box_size": "sm"}),
    "temperature": InputSetting(ui_hints={"text_box_size": "xs"})
}


@tool(
    name="Custom LLM Tool with UI Hints",
    description="This is a custom LLM tool with UI hints.",
    type="custom_llm",
    input_settings=input_settings
)
def my_tool(
    connection: CustomConnection,
    endpoint_name: str,
    api: str,
    temperature: float,
    prompt: PromptTemplate,
    **kwargs
) -> str:
    # Replace with your tool code, customize your own code to handle and use the prompt here.
    # Usually connection contains configs to connect to an API.
    # Not all tools need a connection. You can remove it if you don't need it.
    rendered_prompt = Template(prompt, trim_blocks=True, keep_trailing_newline=True).render(**kwargs)
    return rendered_prompt
