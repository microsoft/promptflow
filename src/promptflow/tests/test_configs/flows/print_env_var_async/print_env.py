import os
import asyncio
from promptflow import tool


@tool
async def get_env_var(key: str):
    await asyncio.sleep(0)
    # get from env var
    return {"value": os.environ.get(key)}
