from promptflow import tool


@tool
def is_even(number: int):
    if number % 2 == 0:
        return {"is_even": True, "message": f"{number} is even number, skip the next node"}
    return {"is_even": False, "message": f"{number} is odd number, go to the next node"}
