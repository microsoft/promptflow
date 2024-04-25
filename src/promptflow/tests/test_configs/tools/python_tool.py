from promptflow.core import ToolProvider, tool
from promptflow.entities import InputSetting
from promptflow.connections import AzureOpenAIConnection

groups = [{
    "name": "Tools",
    "description": "Configure interactive capabilities by selecting tools for the model to use and guiding its tool call decisions.",
    "inputs": ["tools", "tool_choice"],
    "ui_hints": {"display_style": "table"}
}]
input_settings = InputSetting(
    filter_by={
        "input_name": "connection",
        "filter_attribute": "type",
        "values": {
            "AzureOpenAIConnection": {
                "enum": [
                    "chat",
                    "completion"
                ]
            },
            "OpenAIConnection": {
                "enum": [
                    "chat",
                    "completion"
                ]
            },
            "ServerlessConnection": {
                "enum": [
                    "chat"
                ]
            }
        }
    }
)


@tool(
    name="python_tool",
    groups=groups,
    input_settings={
        "input1": input_settings
    }
)
def my_python_tool(input1: str) -> str:
    return 'hello ' + input1
#
#
# @tool
# def my_python_tool_without_name(input1: str) -> str:
#     return 'hello ' + input1
#
#
# class PythonTool(ToolProvider):
#
#     def __init__(self, connection: AzureOpenAIConnection):
#         super().__init__()
#         self.connection = connection
#
#     @tool
#     def python_tool(self, input1: str) -> str:
#         return 'hello ' + input1
