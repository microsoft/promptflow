import json

from promptflow import tool


@tool
def convert_to_dict(input_str: str):
    try:
        return json.loads(input_str)
    except Exception as e:
        print("input is not valid, error: {}".format(e))
        return {"category": "None", "evidence": "None"}
