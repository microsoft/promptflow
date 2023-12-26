from promptflow import tool
import random


@tool
def get_calorie(location: str, weather: str):
    """Get the calories of running for one hour according to the location and weather.
    
    :param location: Location to get calorie from.
    :type location: str
    :param weather: Weather to get calorie from.
    :type weather: str
    """

    return random.randint(100, 200)
