from time import sleep
from promptflow import tool


@tool
def wait(**args) -> int:
    sleep(5)
    return str(args)
