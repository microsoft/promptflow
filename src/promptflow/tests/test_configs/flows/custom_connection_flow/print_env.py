import os

from promptflow import tool
from promptflow.connections import CustomConnection


@tool
def get_env_var(key: str, connection: CustomConnection):
    # get from env var
    return {"value": os.environ.get(key)}
