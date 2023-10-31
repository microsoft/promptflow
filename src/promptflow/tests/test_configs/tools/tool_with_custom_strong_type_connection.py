from promptflow._core.tool import tool
from promptflow.connections import CustomStrongTypeConnection
from promptflow.contracts.types import Secret


class MyCustomConnection(CustomStrongTypeConnection):
    """My custom strong type connection.

    :param api_key: The api key get from "https://xxx.com".
    :type api_key: Secret
    :param api_base: The api base.
    :type api_base: String
    """
    api_key: Secret
    api_base: str = "This is a fake api base."


@tool(name="Tool With Custom Strong Type Connection", description="This is my tool with custom strong type connection.")
def my_tool(connection: MyCustomConnection, input_text: str) -> str:
    # Replace with your tool code.
    # Use custom strong type connection like: connection.api_key, connection.api_base
    return "Hello " + input_text
