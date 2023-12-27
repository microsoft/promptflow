from promptflow import tool
import random


@tool
def get_calorie_by_jogging(duration: float, temperature: float):
    """Estimate the calories burned by jogging based on duration and temperature.

    :param duration: the length of the jogging in hours.
    :type duration: float
    :param temperature: the environment temperature in degrees Celsius.
    :type temperature: float
    """

    return random.randint(50, 200)
