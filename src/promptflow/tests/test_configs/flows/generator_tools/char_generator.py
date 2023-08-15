from promptflow import tool


@tool
def character_generator(text: str):
    """Generate characters from a string."""

    for char in text:
        yield char
