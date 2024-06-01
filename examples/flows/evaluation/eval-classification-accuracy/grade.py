from promptflow.core import tool


@tool
def grade(groundtruth: str, prediction: str):
    return "Correct" if groundtruth.replace(" ", "").lower() == prediction.replace(" ", "").lower() else "Incorrect"
