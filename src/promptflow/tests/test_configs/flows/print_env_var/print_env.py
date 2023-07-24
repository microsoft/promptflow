import os

from promptflow import tool


@tool
def get_env_var(key: str):
    # get from env var
    return {"value": os.environ.get(key)}
