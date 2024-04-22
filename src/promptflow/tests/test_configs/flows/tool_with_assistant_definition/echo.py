from promptflow.core import tool
from promptflow.connections import AzureOpenAIConnection


@tool
def echo(connection: AzureOpenAIConnection, message: str):
    """This tool is used to echo the message back.

    :param message: The message to echo.
    :type message: str
    """
    assert isinstance(connection, AzureOpenAIConnection)
    return message
