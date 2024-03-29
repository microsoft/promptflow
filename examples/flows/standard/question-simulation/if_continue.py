from promptflow.core import tool


@tool
def if_continue(stop_or_continue: str) -> bool:
    if "continue" in stop_or_continue.lower():
        return True
    else:
        return False
