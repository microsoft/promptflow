from promptflow import tool
import random


@tool
def content_safety_check(text: str) -> str:
    return random.choice([True, False])
