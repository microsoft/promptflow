import asyncio
import os
import random

from fastapi import FastAPI

random.seed(42)
app = FastAPI()


@app.get("/")
async def wait_and_return():

    min_wait_time_sec = int(os.getenv("MIN_WAIT_TIME_SEC", 1))
    max_wait_time_sec = int(os.getenv("MAX_WAIT_TIME_SEC", 5))

    # generate a random number of seconds to sleep between min and max.
    random_float = random.uniform(min_wait_time_sec, max_wait_time_sec)
    await asyncio.sleep(random_float)

    # return a message to say just how long the service waited for
    return {
        "total_time_sec": random_float,
        "min_wait_time_sec": min_wait_time_sec,
        "max_wait_time_sec": max_wait_time_sec,
    }
