import random

from promptflow import tool


@tool
def get_current_city():
    """Get current city."""

    return random.choice(["Beijing", "Shanghai"])
