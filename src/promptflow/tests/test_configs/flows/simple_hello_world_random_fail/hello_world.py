from promptflow.core import tool
import random


@tool
def hello_world(name: str) -> str:
    if random.random() < 0.5:
        raise ValueError("Random failure")

    return f"Hello World {name}!"
