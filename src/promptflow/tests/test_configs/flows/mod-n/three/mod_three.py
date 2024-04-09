from promptflow.core import tool


@tool
def mod_three(number: int):
    if number % 3 != 0:
        raise Exception("cannot mod 3!")
    return {"value": number}
