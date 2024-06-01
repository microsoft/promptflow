from promptflow.core import tool


@tool
def grade(groundtruth: str, prediction: str):
    groundtruth = groundtruth.lower().strip('"')
    prediction = prediction.lower().strip('"')
    return "Correct" if groundtruth.replace(" ", "").lower() == prediction.replace(" ", "").lower() else "Incorrect"
