from typing import Union

from utils import ErrorMsg, ResponseFormat, get_text_trunk_score, llm_call

from promptflow import tool
from promptflow.connections import AzureOpenAIConnection, OpenAIConnection


@tool
def validate_and_generate_seed_question(
    connection: Union[OpenAIConnection, AzureOpenAIConnection],
    model: str,
    score_text_trunk_prompt: str,
    score_threshold: float,
    seed_question_prompt: str,
    context: str = None,
    response_format: str = ResponseFormat.JSON,
):
    """
    1. Validates the given text chunk.
    2. Generates a seed question based on the given prompts.

    Returns:
        dict: The generated seed question and text trunk validation result.
    """
    text_trunk_score_res = get_text_trunk_score(
        connection, model, score_text_trunk_prompt, response_format, score_threshold
    )
    if not text_trunk_score_res.pass_validation:
        print(ErrorMsg.INVALID_TEXT_TRUNK.format(context))
        return {"question": "", "validation_res": text_trunk_score_res}

    seed_question = llm_call(connection, model, seed_question_prompt)
    return {"question": seed_question, "validation_res": text_trunk_score_res}
