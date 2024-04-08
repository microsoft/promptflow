from promptflow.core import tool
from promptflow.connections import CustomConnection


@tool
def get_val(key, conn: CustomConnection):
    # get from env var
    print(key)
    if not isinstance(key, dict):
        raise TypeError(f"key must be a dict, got {type(key)}")
    return {"value": f"{key}: {type(key)}"}
