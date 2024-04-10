from promptflow.core import tool


@tool
def validate_inputs(answer: str, context: str):
    # Validate input parameters
    if not (answer and answer.strip() and answer != "None") or not (context and context.strip() and context != "None"):
        raise ValueError("Both 'answer' and 'context' must be non-empty strings.")

    return True
