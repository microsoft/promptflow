import os

from promptflow.core import tool


@tool
def get_env_var(key: str):
    print(os.environ.get(key))
    # get from env var
    return {"value": os.environ.get(key)}
