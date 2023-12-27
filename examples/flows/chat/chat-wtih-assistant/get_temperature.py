


import random

from promptflow import tool


@tool
def get_temperature(location: str, unit: str = "c"):
    """Estimate the current temperature of a given location. The temperature is randomly generated.

    :param location: Location to get the estimated temperature for.
    :type location: str
    :param unit: The unit of the temperature, either 'c' for Celsius or 'f' for Fahrenheit.
                 Defaults to Celsius ('c').
    :type unit: str
    """

    return random.uniform(0, 35)