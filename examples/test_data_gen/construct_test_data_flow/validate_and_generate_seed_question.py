from typing import Union

from utils import llm_call

from promptflow import tool
from promptflow.connections import AzureOpenAIConnection, OpenAIConnection


@tool
def validate_and_generate_seed_question(
        connection: Union[OpenAIConnection, AzureOpenAIConnection],
        model: str,
        validate_context_prompt: str,
        seed_question_prompt: str
):
    """
    1. Validates the given text chunk.  
    2. Generates a seed question based on the given prompts.  
  
    Returns:  
        str: The generated seed question.  
    """
    is_valid = llm_call(connection, model, validate_context_prompt)
    if not is_valid:
        print("invalid text chunk.")
        return ""

    seed_question = llm_call(connection, model, seed_question_prompt)
    return seed_question
