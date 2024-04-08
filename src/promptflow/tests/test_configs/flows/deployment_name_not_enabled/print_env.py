from typing import Union


from promptflow.core import tool
from promptflow.connections import AzureOpenAIConnection, OpenAIConnection


@tool()
def generate_question(
    connection: Union[OpenAIConnection, AzureOpenAIConnection],
    generate_question_prompt: str,
    deployment_name: str = "",
    model: str = "",
    context: str = None,
    temperature: float = 0.2
):
    return {"deployment_name": deployment_name, "model": model}
