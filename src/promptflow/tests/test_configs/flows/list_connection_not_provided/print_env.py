from typing import Union

from promptflow.core import tool
from promptflow.connections import CustomConnection, OpenAIConnection


@tool
def get_env_var(key: str, connection: Union[CustomConnection, OpenAIConnection]):
    # get from env var
    return {"key": key, "connection": connection.type}
