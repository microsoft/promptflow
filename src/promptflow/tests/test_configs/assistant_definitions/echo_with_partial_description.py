from promptflow import tool
from promptflow.connections import AzureOpenAIConnection


@tool
def echo(connection: AzureOpenAIConnection, message: str, message1: str):
    """
    :param connection: This is the connection part.
    :type connection: AzureOpenAIConnection
    :param message: The message to echo.
    :type message: str
    :type message1: str
    """
    assert isinstance(connection, AzureOpenAIConnection)
    return message
