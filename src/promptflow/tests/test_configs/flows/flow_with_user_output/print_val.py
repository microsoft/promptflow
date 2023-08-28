import sys

from promptflow import tool


@tool
def get_val(key):
    # get from env var
    print(key)
    print("user log")
    print("error log", file=sys.stderr)