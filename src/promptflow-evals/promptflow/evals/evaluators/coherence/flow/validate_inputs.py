from promptflow import tool

@tool
def validate_inputs(question: str, answer: str):
    # Validate input parameters
    if not (question and question.strip()) or not (answer and answer.strip()):
        raise ValueError("Both 'question' and 'answer' must be non-empty strings.")

    return True