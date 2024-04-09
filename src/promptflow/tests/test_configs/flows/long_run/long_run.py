import time
from promptflow.core import tool


def f1():
    time.sleep(61)
    return 0


def f2():
    return f1()


@tool
def long_run_func():
    return f2()
