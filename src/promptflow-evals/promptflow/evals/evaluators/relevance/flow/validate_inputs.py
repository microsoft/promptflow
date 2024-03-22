from promptflow import tool

@tool
def validate_inputs(question: str, answer: str, context: str):
    # Validate input parameters
    if not (question and question.strip()) or not (answer and answer.strip()) or not (context and context.strip()):
        raise ValueError("'question', 'answer' and 'context' must be non-empty strings.")

    return True