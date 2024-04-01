from promptflow import tool

@tool
def validate_inputs(answer: str, context: str):
    # Validate input parameters
    if not (answer and answer.strip()) or not (context and context.strip()):
        raise ValueError("Both 'answer' and 'context' must be non-empty strings.")

    return True