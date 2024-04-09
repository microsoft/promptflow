from openai import AsyncAzureOpenAI

from promptflow.core import tool
from promptflow.connections import AzureOpenAIConnection


@tool
async def embedding(connection: AzureOpenAIConnection, input: str, model: str) -> str:
    client = AsyncAzureOpenAI(
        api_key=connection.api_key, azure_endpoint=connection.api_base, api_version=connection.api_version
    )
    resp = await client.embeddings.create(model=model, input=input)
    return resp.data[0].embedding
