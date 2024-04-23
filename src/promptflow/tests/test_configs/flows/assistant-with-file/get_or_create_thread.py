from typing import Union
from promptflow.core import tool
from promptflow.connections import AzureOpenAIConnection, OpenAIConnection
from get_assistant_client import get_assistant_client


@tool
async def get_or_create_thread(conn: Union[AzureOpenAIConnection, OpenAIConnection], thread_id: str):
    if thread_id:
        return thread_id
    cli = await get_assistant_client(conn)
    thread = await cli.beta.threads.create()
    return thread.id