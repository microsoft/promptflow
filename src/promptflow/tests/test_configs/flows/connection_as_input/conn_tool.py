from promptflow import tool
from promptflow.connections import AzureOpenAIConnection


@tool
def conn_tool(conn: AzureOpenAIConnection):
    assert isinstance(conn, AzureOpenAIConnection)
    return conn.api_base
