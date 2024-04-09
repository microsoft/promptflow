from typing import List

from promptflow.core import tool


@tool
def get_val(key):
    # get from env var
    print(key)
    return {"value": f"{key}: {type(key)}"}
