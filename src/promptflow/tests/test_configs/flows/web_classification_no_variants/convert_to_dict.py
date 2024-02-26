import json
import time

from promptflow import tool


@tool
def convert_to_dict(input_str: str):
    try:
        # Sleep for 1.3 seconds
        time.sleep(1.3)
        return json.loads(input_str)
    except Exception as e:
        print("input is not valid, error: {}".format(e))
        return {"category": "None", "evidence": "None"}
