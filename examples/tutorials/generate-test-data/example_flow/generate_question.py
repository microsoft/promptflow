from typing import Union

from utils import llm_call

from promptflow._core.tool import InputSetting
from promptflow.connections import AzureOpenAIConnection, OpenAIConnection
from promptflow.core import tool


@tool(
    input_settings={
        "deployment_name": InputSetting(
            enabled_by="connection",
            enabled_by_type=["AzureOpenAIConnection"],
            capabilities={"completion": False, "chat_completion": True, "embeddings": False},
        ),
        "model": InputSetting(enabled_by="connection", enabled_by_type=["OpenAIConnection"]),
    }
)
def generate_question(
    connection: Union[OpenAIConnection, AzureOpenAIConnection],
    generate_question_prompt: str,
    deployment_name: str = "",
    model: str = "",
    context: str = None,
    temperature: float = 0.2,
):
    """
    Generates a question based on the given context.

    Returns:
        str: The generated seed question.
    """
    # text chunk is not valid, just skip test data gen.
    if not context:
        return ""

    seed_question = llm_call(connection, model, deployment_name, generate_question_prompt, temperature=temperature)
    return seed_question
