import random

from promptflow import tool


@tool
def get_calorie_by_swimming(duration: float, temperature: float):
    """Estimate the calories burned by swimming based on duration and temperature.

    :param duration: the length of the swimming in hours.
    :type duration: float
    :param temperature: the environment temperature in degrees Celsius.
    :type temperature: float
    """
    print(
        f"Figure out the calories burned by swimming, with temperature of {temperature} degrees Celsius, "
        f"and duration of {duration} hours."
    )
    return random.randint(100, 200)
