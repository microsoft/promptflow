from promptflow.core import tool
import asyncio


@tool
async def passthrough_str_and_wait(input1: str, wait_seconds=3, wait_seconds_in_cancellation=1) -> str:
    assert isinstance(input1, str), f"input1 should be a string, got {input1}"
    try:
        print(f"Wait for {wait_seconds} seconds in async function")
        for i in range(wait_seconds):
            print(i)
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        print(f"Async function is cancelled, wait for {wait_seconds_in_cancellation}"
              " in cancellation process")
        for i in range(wait_seconds_in_cancellation):
            print(f"Wait for {i} seconds in async tool cancellation logic")
            await asyncio.sleep(1)
        print(f"End time consuming cancellation process")
        raise
    return input1
