from promptflow.core import tool


@tool
def validate_inputs(question: str, answer: str, context: str):
    # Validate input parameters
    if (
        not (question and question.strip() and question != "None")
        or not (answer and answer.strip() and answer != "None")
        or not (context and context.strip() and context != "None")
    ):
        raise ValueError("'question', 'answer' and 'context' must be non-empty strings.")

    return True
