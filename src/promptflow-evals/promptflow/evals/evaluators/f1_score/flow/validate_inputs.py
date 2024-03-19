from promptflow import tool

@tool
def validate_inputs(answer: str, ground_truth: str):
    if not (answer and answer.strip()) or not (ground_truth and ground_truth.strip()):
        raise ValueError("Both 'answer' and 'ground_truth' must be non-empty strings.")

    return True