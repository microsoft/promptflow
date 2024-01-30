from typing import Union

from utils import ErrorMsg, ResponseFormat, get_text_trunk_validation_res, llm_call

from promptflow import tool
from promptflow.connections import AzureOpenAIConnection, OpenAIConnection


@tool
def validate_and_generate_seed_question(
        connection: Union[OpenAIConnection, AzureOpenAIConnection],
        model_or_deployment_name: str,
        validate_text_trunk_prompt: str,
        seed_question_prompt: str,
        context: str = None,
        response_format: str = ResponseFormat.JSON,
        temperature: float = 1.0,
        max_tokens: int = 512
):
    """
    1. Validates the given text chunk.
    2. Generates a seed question based on the given prompts.

    Returns:
        dict: The generated seed question and text trunk validation result.
    """
    validation_res = get_text_trunk_validation_res(
        connection,
        model_or_deployment_name,
        validate_text_trunk_prompt,
        context,
        response_format,
        temperature,
        max_tokens
    )
    is_valid_text_trunk = validation_res.pass_validation
    if not is_valid_text_trunk:
        print(ErrorMsg.INVALID_TEXT_TRUNK)
        print(f"yaodebug: {validation_res}")
        return {"question": "", "validation_res": validation_res}

    seed_question = llm_call(
        connection,
        model_or_deployment_name,
        seed_question_prompt,
        temperature=temperature,
        max_tokens=max_tokens)
    return {"question": seed_question, "validation_res": validation_res}
