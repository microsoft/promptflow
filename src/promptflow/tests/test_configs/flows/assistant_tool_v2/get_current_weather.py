import random

from promptflow import tool


@tool
def get_current_weather(location: str):
    """Get the weather in location.
    
    :param location: Location to get weather from.
    :type location: str
    """

    return random.choice(["Sunny", "Rainy", "Snowy", "Cloudy", "Windy"])
