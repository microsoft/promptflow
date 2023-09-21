from typing import List

from promptflow import tool


@tool
def get_val(key):
    # get from env var
    print(key)
    return {"value": f"{key}: {type(key)}"}
