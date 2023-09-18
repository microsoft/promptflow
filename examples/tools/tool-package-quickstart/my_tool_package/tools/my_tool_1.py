from promptflow import tool
from my_tool_package.connections import MyFirstConnection


@tool
def my_tool(connection: MyFirstConnection, input_text: str) -> str:
    # Replace with your tool code.
    # Usually connection contains configs to connect to an API.
    # Not all tools need a connection. You can remove it if you don't need it.
    return f"connection_value is MyFirstConnection: {str(isinstance(connection, MyFirstConnection))}"
