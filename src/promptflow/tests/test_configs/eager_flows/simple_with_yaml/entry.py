# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from promptflow import trace
import time


@trace
def hello(name):
    return f"Hello {name}"


@trace
def query():
    """Query for input."""
    time.sleep(1)
    #1/0
    return "gpt"


def my_flow(input_val: str = "gpt") -> str:
    """Simple flow without yaml."""
    print("calling query")
    hello("world")
    #for i in range(3):
    #    query()
    return f"Hello world! {input_val}"


if __name__ == "__main__":
    my_flow()