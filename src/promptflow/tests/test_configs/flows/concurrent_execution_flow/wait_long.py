from time import sleep
from promptflow.core import tool


@tool
def wait(**args) -> int:
    sleep(5)
    return str(args)
