from promptflow import tool


@tool
def read_log(log_path: str):
    try:
        with open(log_path, 'r') as file:
            data = file.read()
        return data
    except Exception as e:
        print("input is not valid, error: {}".format(e))
        return ""