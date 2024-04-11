from promptflow.core import tool


@tool
def print_val(val, origin_val):
    print(val)
    print(origin_val)
    if not isinstance(origin_val, dict):
        raise TypeError(f"key must be a dict, got {type(origin_val)}")
    return val
