from typing import Union

from utils import llm_call

from promptflow import tool
from promptflow.connections import AzureOpenAIConnection, OpenAIConnection


@tool
def generate_ground_truth(
    connection: Union[OpenAIConnection, AzureOpenAIConnection],
    model: str,
    question: str,
    context: str,
    generate_ground_truth_prompt: str,
):
    """
    Generates a ground truth based on the given prompts and context information.

    Returns:
        str: The generated ground truth.
    """
    if question and context:
        return llm_call(connection, model, generate_ground_truth_prompt)
    else:
        return ""
