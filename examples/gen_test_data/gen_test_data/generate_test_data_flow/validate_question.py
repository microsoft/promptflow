from typing import Union

from utils import ErrorMsg, QuestionType, ResponseFormat, get_question_validation_res

from promptflow import tool
from promptflow.connections import AzureOpenAIConnection, OpenAIConnection


@tool
def validate_question(
    connection: Union[OpenAIConnection, AzureOpenAIConnection],
    model_or_deployment_name: str,
    generated_question: str,
    validate_question_prompt: str,
    response_format: str = ResponseFormat.TEXT,
    temperature: float = 1.0,
    max_tokens: int = 512,
):
    """
    1. Validates the given seed question.
    2. Generates a test question based on the given prompts and distribution ratios.

    Returns:
        dict: The generated test question and its type.
    """
    # text trunk is not valid, seed question not generated.
    if not generated_question:
        return {"question": "", "question_type": "", "validation_res": None}

    validation_res = get_question_validation_res(
        connection,
        model_or_deployment_name,
        validate_question_prompt,
        generated_question,
        response_format,
        temperature,
        max_tokens,
    )
    is_valid_seed_question = validation_res.pass_validation
    question = ""
    question_type = ""
    failed_reason = ""
    if not is_valid_seed_question:
        failed_reason = ErrorMsg.INVALID_QUESTION.format(generated_question)
        print(failed_reason)
    else:
        question = generated_question
        question_type = QuestionType.SIMPLE

    return {"question": question, "question_type": question_type, "validation_res": validation_res}
