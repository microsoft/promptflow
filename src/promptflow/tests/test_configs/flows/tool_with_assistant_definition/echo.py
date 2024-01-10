from promptflow import tool
from promptflow.connections import AzureOpenAIConnection


@tool
def echo(predefined_conn: AzureOpenAIConnection, message: str):
    """This tool is used to echo the message back.
    
    :param message: The message to echo.
    :type message: str
    """

    assert isinstance(predefined_conn, AzureOpenAIConnection)
    return message
