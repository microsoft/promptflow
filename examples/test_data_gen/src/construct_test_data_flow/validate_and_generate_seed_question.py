from typing import Union

from utils import is_valid_text_trunk, llm_call

from promptflow import tool
from promptflow.connections import AzureOpenAIConnection, OpenAIConnection


@tool
def validate_and_generate_seed_question(
    connection: Union[OpenAIConnection, AzureOpenAIConnection],
    model: str,
    validate_text_trunk_prompt: str,
    seed_question_prompt: str,
    context: str = None,
):
    """
    1. Validates the given text chunk.
    2. Generates a seed question based on the given prompts.

    Returns:
        str: The generated seed question.
    """
    answer = llm_call(connection, model, validate_text_trunk_prompt)
    if not is_valid_text_trunk(answer, context):
        print("Skipping generating seed question due to invalid text chunk.")
        return ""

    seed_question = llm_call(connection, model, seed_question_prompt)
    return seed_question
