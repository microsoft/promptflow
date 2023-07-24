from promptflow import tool
from promptflow.connections import AzureOpenAIConnection, SerpConnection


@tool
def conn_tool(
    text: str,
    conn1: AzureOpenAIConnection,
    conn2: AzureOpenAIConnection,
    serp_conn: SerpConnection,
):
    assert isinstance(conn1, AzureOpenAIConnection)
    assert isinstance(conn2, AzureOpenAIConnection)
    assert isinstance(serp_conn, SerpConnection)
    return text
