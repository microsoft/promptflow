import os
import time

import requests
from promptflow.core import tool


@tool
def my_python_tool(node1: str, node2: str, node3: str) -> str:

    start_time = time.time()

    # make a call to the mock endpoint
    url = os.getenv("MOCK_API_ENDPOINT", None)
    if url is None:
        raise RuntimeError("Failed to read MOCK_API_ENDPOINT env var.")

    # respond with the service call and tool total times
    response = requests.get(url)
    if response.status_code == 200:
        response_dict = response.json()
        end_time = time.time()
        response_dict["pf_node_time_sec"] = end_time - start_time
        response_dict["type"] = "pf_dag_sync"
        return response_dict
    else:
        raise RuntimeError(f"Failed call to {url}: {response.status_code}")
