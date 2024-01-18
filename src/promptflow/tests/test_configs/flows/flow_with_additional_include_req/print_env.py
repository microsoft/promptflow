import os

from promptflow import tool


@tool
def get_env_var(key: str):
    from evals import __version__
    print(os.environ.get(key))

    # get from env var
    return {"value": os.environ.get(key)}
