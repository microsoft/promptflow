from promptflow import ToolProvider, tool
from my_tool_package.connections import MyFirstConnection


class MyTool(ToolProvider):
    """
    Doc reference :
    """

    def __init__(self, connection: MyFirstConnection):
        super().__init__()
        self.connection = connection

    @tool
    def my_tool(self, input_text: str) -> str:
        # Replace with your tool code.
        # Usually connection contains configs to connect to an API.
        # Not all tools need a connection. You can remove it if you don't need it.
        return input_text + self.connection.api_base
