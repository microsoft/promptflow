import os
from openai import AzureOpenAI

from promptflow import tool
from promptflow.connections import AzureOpenAIConnection


@tool
def completion(connection: AzureOpenAIConnection, prompt: str) -> str:
    os.environ["AZURE_OPENAI_API_KEY"] = connection.api_key
    os.environ["OPENAI_API_VERSION"] = connection.api_version
    os.environ["AZURE_OPENAI_ENDPOINT"] = connection.api_base
    client = AzureOpenAI()
    response = client.completions.create(model="text-davinci-003", prompt=prompt)
    return response.choices[0].text
