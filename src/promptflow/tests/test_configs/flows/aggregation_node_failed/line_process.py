from promptflow.core import tool


@tool
def line_process(groundtruth: str, prediction: str):
    processed_result = groundtruth + prediction
    return processed_result
