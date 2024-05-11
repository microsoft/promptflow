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
def generate_suggested_answer(
    connection: Union[OpenAIConnection, AzureOpenAIConnection],
    question: str,
    context: str,
    generate_suggested_answer_prompt: str,
    deployment_name: str = "",
    model: str = "",
    temperature: float = 0.2,
):
    """
    Generates a suggested answer based on the given prompts and context information.

    Returns:
        str: The generated suggested answer.
    """
    if question and context:
        return llm_call(
            connection,
            model,
            deployment_name,
            generate_suggested_answer_prompt,
            temperature=temperature,
        )
    else:
        return ""
