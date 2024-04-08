from typing import Union


from promptflow.core import tool
from promptflow._core.tool import InputSetting
from promptflow.connections import AzureOpenAIConnection, OpenAIConnection


@tool(input_settings={
    "deployment_name": InputSetting(enabled_by="connection", enabled_by_type=["AzureOpenAIConnection"], capabilities={
            "completion": False,
            "chat_completion": True,
            "embeddings": False
          }),
    "model": InputSetting(enabled_by="connection", enabled_by_type=["OpenAIConnection"]),
})
def generate_question(
    connection: Union[OpenAIConnection, AzureOpenAIConnection],
    generate_question_prompt: str,
    deployment_name: str = "",
    model: str = "",
    context: str = None,
    temperature: float = 0.2
):
    return {"deployment_name": deployment_name, "model": model}
