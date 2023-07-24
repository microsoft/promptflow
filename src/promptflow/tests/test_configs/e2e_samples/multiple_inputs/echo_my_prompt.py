from utils.utils import add
from promptflow import tool
from promptflow.connections import AzureOpenAIConnection


@tool
def my_python_tool(input1: str, unused: AzureOpenAIConnection = None) -> str:
    return add('Prompt: ', input1)
