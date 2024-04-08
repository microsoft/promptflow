from promptflow.core import tool


@tool
def mod_two(number: int):
    if number % 2 != 0:
        raise Exception("cannot mod 2!")
    return {"value": number}
