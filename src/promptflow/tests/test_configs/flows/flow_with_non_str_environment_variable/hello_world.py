import time

from promptflow.core import tool


@tool
def hello_world(name: str) -> str:
    # Sleep for 1.2 seconds
    time.sleep(1.2)
    return f"Hello World {name}!"
