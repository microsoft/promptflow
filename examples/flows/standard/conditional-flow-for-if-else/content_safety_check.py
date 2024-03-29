from promptflow.core import tool
import random


@tool
def content_safety_check(text: str) -> str:
    # You can use a content safety node to replace this tool.
    return random.choice([True, False])
