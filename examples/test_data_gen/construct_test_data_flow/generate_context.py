from typing import Union

from utils import is_valid_question, llm_call

from promptflow import tool
from promptflow.connections import AzureOpenAIConnection, OpenAIConnection


@tool
def generate_context(
    connection: Union[OpenAIConnection, AzureOpenAIConnection],
    model: str,
    question_info: dict,
    generate_context_prompt: str,
    validate_question_prompt: str,
) -> str:
    """
    Generates a context based on the given prompts and question information.

    Returns:
        str: The generated context.
    """
    if not question_info:
        return ""
    question = question_info["question"]
    question_type = question_info["question_type"]
    if not question or (
        question_type != "simple" and not is_valid_question(connection, model, validate_question_prompt)
    ):
        return ""

    return llm_call(connection, model, generate_context_prompt)
