from typing import Union

from utils import ErrorMsg, ResponseFormat, get_text_chunk_score

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
def validate_text_chunk(
    connection: Union[OpenAIConnection, AzureOpenAIConnection],
    score_text_chunk_prompt: str,
    score_threshold: float,
    deployment_name: str = "",
    model: str = "",
    context: str = None,
    response_format: str = ResponseFormat.TEXT,
    temperature: float = 0.2,
):
    """
    Validates the given text chunk. If the validation fails, return an empty context and the validation result.

    Returns:
        dict: Text chunk context and its validation result.
    """
    text_chunk_score_res = get_text_chunk_score(
        connection,
        model,
        deployment_name,
        score_text_chunk_prompt,
        response_format,
        score_threshold,
        temperature,
    )
    if not text_chunk_score_res.pass_validation:
        print(ErrorMsg.INVALID_TEXT_CHUNK.format(context))
        return {"context": "", "validation_res": text_chunk_score_res._asdict()}

    return {"context": context, "validation_res": text_chunk_score_res._asdict()}
