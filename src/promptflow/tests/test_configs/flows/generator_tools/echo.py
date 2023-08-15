from promptflow import tool
from char_generator import character_generator


@tool
def echo(text):
    """Echo the input string."""

    echo_text = "Echo - " + "".join(character_generator(text))
    return echo_text
