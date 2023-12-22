import random

from promptflow import tool
from promptflow.connections import AzureOpenAIConnection


@tool
def get_current_location(preset_int: int, preset_conn: AzureOpenAIConnection):
    """Get the location of the current user.

    :param preset_int: The preset int.
    :type preset_int: int
    :param preset_conn: The preset connection.
    :type preset_conn: AzureOpenAIConnection
    """

    return random.choice(["Beijing", "Shanghai"])
