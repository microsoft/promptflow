import random

from promptflow import tool


@tool
def get_current_location():
    """Get the location of the current user."""

    return random.choice(["Beijing", "Shanghai"])
