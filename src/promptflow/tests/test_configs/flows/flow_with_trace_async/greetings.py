import asyncio
from promptflow.core import tool
from promptflow.tracing import trace


@trace
async def is_valid_name(name):
    await asyncio.sleep(0.5)
    return len(name) > 0


@trace
async def get_user_name(user_id):
    await asyncio.sleep(0.5)
    user_name = f"User {user_id}"
    if not await is_valid_name(user_name):
        raise ValueError(f"Invalid user name: {user_name}")

    return user_name


@trace
async def format_greeting(user_name):
    await asyncio.sleep(0.5)
    return f"Hello, {user_name}!"


@tool
async def greetings(user_id):
    user_name = await get_user_name(user_id)
    greeting = await format_greeting(user_name)
    print(greeting)
    return {"greeting": greeting}
