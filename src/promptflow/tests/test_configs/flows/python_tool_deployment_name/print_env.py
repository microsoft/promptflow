from promptflow import tool


@tool
def get_result(key: str, deployment_name: str, model: str):
    # get from env var
    return {"key": key, "deployment_name": deployment_name, "model": model}
