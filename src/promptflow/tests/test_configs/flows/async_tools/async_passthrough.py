from promptflow.core import tool
import asyncio


@tool
async def passthrough_str_and_wait(input1: str, wait_seconds=3) -> str:
    assert isinstance(input1, str), f"input1 should be a string, got {input1}"
    print(f"Wait for {wait_seconds} seconds in async function")
    for i in range(wait_seconds):
        print(i)
        await asyncio.sleep(1)
    return input1
