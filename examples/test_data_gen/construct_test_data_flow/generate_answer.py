from typing import Union

from utils import llm_call

from promptflow import tool
from promptflow.connections import OpenAIConnection, AzureOpenAIConnection


@tool
def generate_answer(
        connection: Union[OpenAIConnection, AzureOpenAIConnection],
        model: str,
        context: str,
        generate_answer_prompt: str
):
    """  
    Generates a answer based on the given prompts and context information.  

    Returns:  
        str: The generated answer.  
    """
    if context is None:
        return None

    return llm_call(connection, model, generate_answer_prompt)
