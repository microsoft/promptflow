from typing import Union

from utils import llm_call, is_valid_question

from promptflow import tool
from promptflow.connections import OpenAIConnection, AzureOpenAIConnection


@tool
def validate_and_generate_context(
        connection: Union[OpenAIConnection, AzureOpenAIConnection],
        model: str,
        question_info: dict,
        generate_context_prompt: str,
        validate_question_prompt: str
):
    """
    1. Validates the given question.
    2. Generates a context based on the given prompts and question information.  

    Returns:  
        str: The generated context.  
    """
    question = question_info["question"]
    question_type = question_info["question_type"]
    if question == "" or (
            question_type != "simple" and not is_valid_question(connection, model, validate_question_prompt)):
        return ""

    return llm_call(connection, model, generate_context_prompt)
