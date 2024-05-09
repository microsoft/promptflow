from promptflow.core import tool
# import asyncio

@tool
async def echo(count):
    """yield the input string."""

    echo_text = "Echo - "
    for i in range(count):
        # # suspend and sleep a moment
        # await asyncio.sleep(0.1)
        # yield a value to the caller
        yield f"{echo_text}{i}"