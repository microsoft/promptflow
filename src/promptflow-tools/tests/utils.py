import json


def is_json_serializable(data, function_name):
    try:
        json.dumps(data)
    except TypeError:
        raise TypeError(f"{function_name} output is not JSON serializable!")
