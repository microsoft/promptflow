from promptflow.core import tool


@tool
def convert_to_dict(input_list: list):
    for input in input_list:
        try:
            return {"category": input["category"], "evidence": input["evidence"]}
        except Exception as e:
            print("input is not valid, error: {}".format(e))
            return {"category": "None", "evidence": "None"}
