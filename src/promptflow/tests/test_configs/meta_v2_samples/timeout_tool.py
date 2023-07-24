from json import tool
from time import sleep

sleep(15)


@tool
def timeout_tool():
    print("timeout tool")
