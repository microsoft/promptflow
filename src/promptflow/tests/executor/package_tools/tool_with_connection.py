from dataclasses import dataclass

from promptflow._core.tools_manager import register_connections
from promptflow.contracts.types import Secret
from promptflow.core import tool


@dataclass
class TestConnection:
    name: str
    secret: Secret


register_connections(TestConnection)


@tool
def tool_with_test_conn(conn: TestConnection):
    assert isinstance(conn, TestConnection)
    return conn.name + conn.secret
