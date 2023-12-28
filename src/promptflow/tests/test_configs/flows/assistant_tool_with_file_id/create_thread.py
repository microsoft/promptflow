from openai import AsyncOpenAI

from promptflow import tool
from promptflow.connections import OpenAIConnection


@tool
async def create_thread(conn: OpenAIConnection):
    cli = AsyncOpenAI(api_key=conn.api_key, organization=conn.organization)
    thread = await cli.beta.threads.create()
    return thread.id
