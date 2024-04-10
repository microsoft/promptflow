import random
import time

from promptflow.core import tool


@tool
def get_temperature(city: str, unit: str = "c"):
    """Estimate the current temperature of a given city.

    :param city: city to get the estimated temperature for.
    :type city: str
    :param unit: the unit of the temperature, either 'c' for Celsius or 'f' for Fahrenheit.
                 Defaults to Celsius ('c').
    :type unit: str
    """

    # Generating a random number between 0.2 and 1 for tracing purpose
    time.sleep(random.uniform(0.2, 1))

    return random.uniform(0, 35)
