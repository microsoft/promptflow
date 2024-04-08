import threading
from time import sleep
from promptflow.core import tool


@tool
def wait(**kwargs) -> int:
    if kwargs["throw_exception"]:
        raise Exception("test exception")
    for i in range(10):
        print(f"Thread {threading.get_ident()} write test log number {i}")
    sleep(2)
    return 0
