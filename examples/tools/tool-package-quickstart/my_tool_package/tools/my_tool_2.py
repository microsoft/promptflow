from promptflow.core import ToolProvider, tool
from promptflow.connections import CustomConnection


class MyTool(ToolProvider):
    """
    Doc reference :
    """

    def __init__(self, connection: CustomConnection):
        super().__init__()
        self.connection = connection

    @tool
    def my_tool(self, input_text: str) -> str:
        # Replace with your tool code.
        # Usually connection contains configs to connect to an API.
        # Use CustomConnection is a dict. You can use it like: connection.api_key, connection.api_base
        # Not all tools need a connection. You can remove it if you don't need it.
        return "Hello " + input_text
