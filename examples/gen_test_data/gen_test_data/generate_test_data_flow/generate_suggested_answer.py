from typing import Union

from utils import llm_call

from promptflow import tool
from promptflow.connections import AzureOpenAIConnection, OpenAIConnection


@tool
def generate_suggested_answer(
    connection: Union[OpenAIConnection, AzureOpenAIConnection],
    model_or_deployment_name: str,
    question: str,
    context: str,
    generate_suggested_answer_prompt: str,
    temperature: float = 0.2
):
    """
    Generates a suggested answer based on the given prompts and context information.

    Returns:
        str: The generated suggested answer.
    """
    if question and context:
        return llm_call(
            connection,
            model_or_deployment_name,
            generate_suggested_answer_prompt,
            temperature=temperature,
        )
    else:
        return ""
