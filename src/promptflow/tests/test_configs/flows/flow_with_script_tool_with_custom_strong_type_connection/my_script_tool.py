from promptflow import tool
from promptflow.connections import CustomStrongTypeConnection, CustomConnection
from promptflow.contracts.types import Secret


class MyCustomConnection(CustomStrongTypeConnection):
    """My custom strong type connection.

    :param api_key: The api key.
    :type api_key: String
    :param api_base: The api base.
    :type api_base: String
    """
    api_key: Secret
    api_url: str = "This is a fake api url."


@tool
def my_tool(connection: MyCustomConnection, input_param: str) -> str:
    # Replace with your tool code.
    # Use custom strong type connection like: connection.api_key, connection.api_url
    return f"connection_value is MyCustomConnection: {str(isinstance(connection, MyCustomConnection))}"
