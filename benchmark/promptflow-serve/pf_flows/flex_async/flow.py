import asyncio
import os
import time
from pathlib import Path

import aiohttp

BASE_DIR = Path(__file__).absolute().parent


class ChatFlow:
    def __init__(self):
        pass

    async def __call__(self, question: str, chat_history: list) -> str:  # noqa: B006

        node_instance1 = Node()
        node_instance2 = Node()
        node_instance3 = Node()

        # create a list of tasks
        tasks = [
            self.call_node(node_instance1),
            self.call_node(node_instance2),
            self.call_node(node_instance3)
        ]

        # simulate calling parallel nodes
        await asyncio.gather(*tasks)

        chat_history = chat_history or []
        start_time = time.time()

        # make a call to the mock endpoint
        url = os.getenv("MOCK_API_ENDPOINT", None)
        if url is None:
            raise RuntimeError("Failed to read MOCK_API_ENDPOINT env var.")

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    response_dict = await response.json()
                    end_time = time.time()
                    response_dict["pf_node_time_sec"] = end_time - start_time
                    response_dict["type"] = "pf_flex_async"
                    return response_dict
                else:
                    raise RuntimeError(f"Failed call to {url}: {response.status}")

    async def call_node(self, node_instance: any):
        await node_instance()


class Node:
    def __init__(self):
        pass

    async def __call__(self) -> str:  # noqa: B006
        await asyncio.sleep(0.25)
        return "completed"
