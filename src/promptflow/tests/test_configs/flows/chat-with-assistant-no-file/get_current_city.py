import random
import time

from promptflow.core import tool


@tool
def get_current_city():
    """Get current city."""

    # Generating a random number between 0.2 and 1 for tracing purpose
    time.sleep(random.uniform(0.2, 1))

    return random.choice(["Beijing", "Shanghai"])
