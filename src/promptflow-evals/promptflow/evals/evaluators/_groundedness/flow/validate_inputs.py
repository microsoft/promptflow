from promptflow.core import tool


@tool
def validate_inputs(question: str, answer: str, context: str):
    # Validate input parameters
    if not (context and context.strip() and context != "None") or not (answer and answer.strip() and answer != "None"):
        raise ValueError("Both 'context' and 'answer' must be non-empty strings.")

    return True
