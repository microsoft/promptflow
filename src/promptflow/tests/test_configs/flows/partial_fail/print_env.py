import os

from promptflow import tool


@tool
def get_env_var(key: str):
    if key == "raise":
        raise Exception("expected raise!")

    print(os.environ.get(key))
    # get from env var
    return {"value": os.environ.get(key)}
