from promptflow.core import tool


@tool
def nan_inf(number: int):
    print(number)
    return {"nan": float("nan"), "inf": float("inf")}
