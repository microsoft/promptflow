from promptflow import tool
import random


@tool
def get_calorie_by_jogging(duration: float, temperature: float):
    """Estimate the calories burned by jogging based on duration and temperature.

    :param duration: The length of the jogging in hour.
    :type duration: float
    :param temperature: The environment temperature in degrees celsius.
    :type temperature: float
    """

    return random.uniform(50, 200)
