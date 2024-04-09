import os

from promptflow.core import tool
from promptflow.connections import CustomConnection


@tool
def get_env_var(key: str, connection: CustomConnection):
    # get from env var
    return {"key": key, "connection": connection.type}
