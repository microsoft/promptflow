from typing import Union
from openai import AsyncAzureOpenAI, AsyncOpenAI
from promptflow.tracing import trace
from promptflow.connections import AzureOpenAIConnection, OpenAIConnection

@trace
async def get_assistant_client(conn:  Union[AzureOpenAIConnection, OpenAIConnection]):
    if isinstance(conn, AzureOpenAIConnection):
        cli = AsyncAzureOpenAI(
            api_key=conn.api_key,  
            api_version=conn.api_version,
            azure_endpoint = conn.api_base,
        )
    elif isinstance(conn, OpenAIConnection):
        cli = AsyncOpenAI(api_key=conn.api_key, organization=conn.organization)
    else:
        raise Exception(f"Unsupported connection type for assistant: {type(conn)}")
    return cli