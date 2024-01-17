from typing import Union

from utils import llm_call, is_valid_question

from promptflow import tool
from promptflow.connections import OpenAIConnection, AzureOpenAIConnection


@tool
def generate_context(
        connection: Union[OpenAIConnection, AzureOpenAIConnection],
        model: str,
        question_info: dict,
        generate_context_prompt: str,
        score_question_prompt: str
):
    """  
    Generates a context based on the given prompts and question information.  

    Returns:  
        str: The generated context.  
    """
    question = question_info["question"]
    question_type = question_info["question_type"]
    if question is None or (
            question_type != "simple" and not is_valid_question(connection, model, score_question_prompt)):
        return None

    return llm_call(connection, model, generate_context_prompt)
