from promptflow import tool
from promptflow.connections import AzureOpenAIConnection


@tool
def sample_tool(connection: AzureOpenAIConnection, input_int: int, input_str: str):
    """This is a sample tool.

    :param input_int: This is a sample input int.
    :type input_int: int
    :param input_str: This is a sample input str.
    :type input_str: str
    """
    assert isinstance(connection, AzureOpenAIConnection)
    assert "mock" in connection.api_key
    assert "mock" in connection.api_base
    return input_int, input_str
