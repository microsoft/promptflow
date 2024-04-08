import json
import time

from promptflow.core import tool


# use this to test the timeout
time.sleep(2)


@tool
def convert_to_dict(input_str: str):
    try:
        return json.loads(input_str)
    except Exception as e:
        print("input is not valid, error: {}".format(e))
        return {"category": "None", "evidence": "None"}
