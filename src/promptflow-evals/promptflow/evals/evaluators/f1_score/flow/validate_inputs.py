from promptflow.core import tool


@tool
def validate_inputs(answer: str, ground_truth: str):
    if not (answer and answer.strip() and answer != "None") or not (
        ground_truth and ground_truth.strip() and ground_truth != "None"
    ):
        raise ValueError("Both 'answer' and 'ground_truth' must be non-empty strings.")

    return True
