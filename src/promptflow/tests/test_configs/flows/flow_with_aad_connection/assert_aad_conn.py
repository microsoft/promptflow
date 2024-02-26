from promptflow import tool
from promptflow.connections import AzureOpenAIConnection


@tool
def assert_aad_conn(conn: AzureOpenAIConnection) -> str:
    print(conn.api_key)
    assert conn.auth_mode == "meid_token"
    assert not conn.api_key
    return conn.auth_mode
