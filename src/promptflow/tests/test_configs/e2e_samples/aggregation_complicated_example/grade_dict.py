from promptflow import tool


@tool
def grade(groundtruth: str, prediction: str):
    grade = "Correct" if groundtruth.lower() == prediction.lower() else "Incorrect"
    return {
        "grade": {"value": grade},
    }
