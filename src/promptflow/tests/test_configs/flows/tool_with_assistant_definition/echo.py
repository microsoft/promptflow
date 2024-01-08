from promptflow import tool


@tool
def echo(message: str):
    """This tool is used to echo the message back.
    
    :param message: The message to echo.
    :type message: str
    """
    return message
