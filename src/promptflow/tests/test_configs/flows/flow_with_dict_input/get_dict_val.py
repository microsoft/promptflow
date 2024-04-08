from promptflow.core import tool


@tool
def get_dict_val(key):
    # get from env var
    print(key)
    if not isinstance(key, dict):
        raise TypeError(f"key must be a dict, got {type(key)}")
    return {"value": f"{key}: {type(key)}", "origin_value": key}
