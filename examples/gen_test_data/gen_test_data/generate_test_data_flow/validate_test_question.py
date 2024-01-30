from typing import Union

from utils import QuestionType, get_question_validation_res

from promptflow import tool
from promptflow.connections import AzureOpenAIConnection, OpenAIConnection


@tool
def validate_test_question(
    connection: Union[OpenAIConnection, AzureOpenAIConnection],
    model_or_deployment_name: str,
    question_info: dict,
    # generate_context_prompt: str,
    validate_question_prompt: str,
    temperature: float = 1.0,
    max_tokens: int = 512
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

    validation_res = get_question_validation_res(connection, model_or_deployment_name, validate_question_prompt, question, temperature, max_tokens)
    is_valid_test_question = validation_res.pass_validation
    if not is_valid_test_question:
        print(f"Invalid test question: {question}")
        return ""
    else:
        return question
