from typing import Union

from utils import ErrorMsg, QuestionType, ResponseFormat, get_question_validation_res

from promptflow._core.tool import InputSetting
from promptflow.connections import AzureOpenAIConnection, OpenAIConnection
from promptflow.core import tool


@tool(
    input_settings={
        "deployment_name": InputSetting(
            enabled_by="connection",
            enabled_by_type=["AzureOpenAIConnection"],
            capabilities={"completion": False, "chat_completion": True, "embeddings": False},
        ),
        "model": InputSetting(enabled_by="connection", enabled_by_type=["OpenAIConnection"]),
    }
)
def validate_question(
    connection: Union[OpenAIConnection, AzureOpenAIConnection],
    generated_question: str,
    validate_question_prompt: str,
    deployment_name: str = "",
    model: str = "",
    response_format: str = ResponseFormat.TEXT,
    temperature: float = 0.2,
):
    """
    1. Validates the given seed question.
    2. Generates a test question based on the given prompts and distribution ratios.

    Returns:
        dict: The generated test question and its type.
    """
    # text chunk is not valid, seed question not generated.
    if not generated_question:
        return {"question": "", "question_type": "", "validation_res": None}

    validation_res = get_question_validation_res(
        connection,
        model,
        deployment_name,
        validate_question_prompt,
        generated_question,
        response_format,
        temperature,
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

    return {"question": question, "question_type": question_type, "validation_res": validation_res._asdict()}
