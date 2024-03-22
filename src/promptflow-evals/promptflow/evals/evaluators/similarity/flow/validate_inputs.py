from promptflow import tool

@tool
def validate_inputs(question: str, answer: str, ground_truth: str):
    # Validate input parameters
    if not (question and question.strip()) or not (answer and answer.strip()) or not (ground_truth and ground_truth.strip()):
        raise ValueError("'question', 'answer' and 'ground_truth' must be non-empty strings.")

    return True