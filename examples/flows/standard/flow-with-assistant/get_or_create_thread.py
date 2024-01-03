from openai import AsyncOpenAI

from promptflow import tool
from promptflow.connections import OpenAIConnection


@tool
async def get_or_create_thread(conn: OpenAIConnection, thread_id: str):
    if thread_id:
        return thread_id
    cli = AsyncOpenAI(api_key=conn.api_key, organization=conn.organization)
    thread = await cli.beta.threads.create()
    return thread.id
