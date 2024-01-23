from typing import Union

from utils import QuestionType, is_valid_question

from promptflow import tool
from promptflow.connections import AzureOpenAIConnection, OpenAIConnection


@tool
def validate_test_question(
    connection: Union[OpenAIConnection, AzureOpenAIConnection],
    model: str,
    question_info: dict,
    # generate_context_prompt: str,
    validate_question_prompt: str,
):
    """
    1. Validates the given question.
    2. Generates a context based on the given prompts and question information.

    Returns:
        str: The generated context.
    """
    question = question_info["question"]
    question_type = question_info["question_type"]
    if not question:
        return ""
    # if question type is simple, the question is validated, no need to validate again.
    if question_type == QuestionType.SIMPLE:
        return question
    is_valid_test_question = is_valid_question(connection, model, validate_question_prompt, question)
    if not is_valid_test_question:
        print(f"Invalid test question: {question}")
        return ""
    else:
        return question
