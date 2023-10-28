from promptflow import ToolProvider, tool
from promptflow.connections import AzureOpenAIConnection


@tool(name="python_tool")
def my_python_tool(input1: str) -> str:
    return 'hello ' + input1


@tool
def my_python_tool_without_name(input1: str) -> str:
    return 'hello ' + input1


class PythonTool(ToolProvider):

    def __init__(self, connection: AzureOpenAIConnection):
        super().__init__()
        self.connection = connection

    @tool
    def python_tool(self, input1: str) -> str:
        return 'hello ' + input1
