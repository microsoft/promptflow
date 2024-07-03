import os
import time

import aiohttp
from promptflow.core import tool


@tool
async def my_python_tool(node1: str, node2: str, node3: str) -> str:

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
                response_dict["type"] = "pf_dag_async"
                return response_dict
            else:
                raise RuntimeError(f"Failed call to {url}: {response.status}")
