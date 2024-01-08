import random

from promptflow import tool


@tool
def get_temperature(city: str, unit: str = "c"):
    """Estimate the current temperature of a given city.

    :param city: city to get the estimated temperature for.
    :type city: str
    :param unit: the unit of the temperature, either 'c' for Celsius or 'f' for Fahrenheit.
                 Defaults to Celsius ('c').
    :type unit: str
    """

    return random.uniform(0, 35)
