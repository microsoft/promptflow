from promptflow import tool


@tool
def multiply(a: int, b: int):
    """Multiply two numbers.
    
    :param a: First number.
    :type a: int
    :param b: Second number.
    :type b: int
    """

    return a * b
