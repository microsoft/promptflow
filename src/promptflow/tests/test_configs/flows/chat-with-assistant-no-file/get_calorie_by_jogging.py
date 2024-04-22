import random
import time

from promptflow.core import tool


@tool
def get_calorie_by_jogging(duration: float, temperature: float):
    """Estimate the calories burned by jogging based on duration and temperature.

    :param duration: the length of the jogging in hours.
    :type duration: float
    :param temperature: the environment temperature in degrees Celsius.
    :type temperature: float
    """
    print(
        f"Figure out the calories burned by jogging, with temperature of {temperature} degrees Celsius, "
        f"and duration of {duration} hours."
    )

    # Generating a random number between 0.2 and 1 for tracing purpose
    time.sleep(random.uniform(0.2, 1))

    return random.randint(50, 100)
