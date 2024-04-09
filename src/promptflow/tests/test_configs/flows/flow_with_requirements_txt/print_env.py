import os

from promptflow.core import tool


@tool
def get_env_var(key: str):
    from langchain import __version__

    print(__version__)
    print(os.environ.get(key))
    # get from env var
    return {"value": os.environ.get(key)}
