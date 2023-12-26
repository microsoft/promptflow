import random

from promptflow import tool
from promptflow.connections import AzureOpenAIConnection


@tool
def get_current_location(predefined_input: int):
    """Get the location of the current user.

    :param predefined_input: The preset int.
    :type predefined_input: int
    """

    return random.choice(["Beijing", "Shanghai"])
