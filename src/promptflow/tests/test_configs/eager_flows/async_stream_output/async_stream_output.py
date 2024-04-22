# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import asyncio

async def my_async_genertor():
    for c in "Hello world! ":
        await asyncio.sleep(1)
        yield c

async def my_flow(input_val: str = "gpt"):
    return my_async_genertor()
