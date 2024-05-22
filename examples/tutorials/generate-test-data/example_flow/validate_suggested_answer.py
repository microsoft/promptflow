from typing import Union

from utils import ErrorMsg, get_suggested_answer_validation_res

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
@tool
def validate_suggested_answer(
    connection: Union[OpenAIConnection, AzureOpenAIConnection],
    suggested_answer: str,
    validate_suggested_answer_prompt: str,
    deployment_name: str = "",
    model: str = "",
    temperature: float = 0.2,
    response_format: str = "text",
):
    """
    1. Validates the given suggested answer.

    Returns:
        dict: The generated suggested answer and its validation result.
    """
    if not suggested_answer:
        return {"suggested_answer": "", "validation_res": None}

    validation_res = get_suggested_answer_validation_res(
        connection,
        model,
        deployment_name,
        validate_suggested_answer_prompt,
        suggested_answer,
        temperature,
        response_format=response_format,
    )
    is_valid_gt = validation_res.pass_validation
    failed_reason = ""
    if not is_valid_gt:
        failed_reason = ErrorMsg.INVALID_ANSWER.format(suggested_answer)
        print(failed_reason)
        suggested_answer = ""

    return {"suggested_answer": suggested_answer, "validation_res": validation_res._asdict()}
