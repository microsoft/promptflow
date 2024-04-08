from promptflow.core import tool
from promptflow.connections import AzureOpenAIConnection


@tool
def assert_aad_conn(conn: AzureOpenAIConnection) -> str:
    assert conn.auth_mode == "meid_token"
    assert not conn.api_key, f"expected api_key to be empty, but not"
    return conn.auth_mode
