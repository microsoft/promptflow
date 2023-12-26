# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import asyncio
from promptflow import flow, trace
from promptflow.tools.aoai import chat


@trace
async def sleep(i):
    import time
    print(f"Task {i} started at {time.strftime('%X')}")
    await asyncio.sleep(i)
    print(f"Task {i} finished at {time.strftime('%X')}")


@trace
async def chat():
    # call sleep 5 times
    async with asyncio.TaskGroup() as tg:
        for i in range(1, 6):
            tg.create_task(sleep(i))


@flow
def flow_entry(prompt: str):
    # call async function chat
    asyncio.run(chat())

    return {"val1": "1", "val2": "2"}


if __name__ == "__main__":
    flow_entry(prompt="Hello, world!")
