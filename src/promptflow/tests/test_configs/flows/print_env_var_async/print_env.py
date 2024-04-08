import os
import asyncio
from promptflow.core import tool


@tool
async def get_env_var(key: str):
    await asyncio.sleep(1)
    # get from env var
    return {"value": os.environ.get(key)}
