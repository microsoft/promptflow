from promptflow.core import tool


@tool
def validate_inputs(question: str, answer: str):
    # Validate input parameters
    if not (question and question.strip() and question != "None") or not (
        answer and answer.strip() and answer != "None"
    ):
        raise ValueError("Both 'question' and 'answer' must be non-empty strings.")

    return True
