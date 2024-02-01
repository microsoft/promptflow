from typing import Union

from utils import ErrorMsg, ResponseFormat, get_text_trunk_score

from promptflow import tool
from promptflow.connections import AzureOpenAIConnection, OpenAIConnection


@tool
def validate_text_trunk(
    connection: Union[OpenAIConnection, AzureOpenAIConnection],
    model_or_deployment_name: str,
    score_text_trunk_prompt: str,
    score_threshold: float,
    context: str = None,
    response_format: str = ResponseFormat.JSON,
    temperature: float = 1.0,
    max_tokens: int = 512,
):
    """
    Validates the given text chunk. If the validation fails, return an empty context and the validation result.

    Returns:
        dict: Text trunk context and its validation result.
    """
    text_trunk_score_res = get_text_trunk_score(
        connection,
        model_or_deployment_name,
        score_text_trunk_prompt,
        response_format,
        score_threshold,
        temperature,
        max_tokens,
    )
    if not text_trunk_score_res.pass_validation:
        print(ErrorMsg.INVALID_TEXT_TRUNK.format(context))
        return {"context": "", "validation_res": text_trunk_score_res}

    return {"context": context, "validation_res": text_trunk_score_res}
