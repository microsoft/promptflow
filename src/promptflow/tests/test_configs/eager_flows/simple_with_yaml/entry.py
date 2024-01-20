# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from promptflow import trace
import time


@trace
def hello(name):
    return f"Hello {name}"


@trace
def stream():
    for i in range(3):
        yield str(i)


@trace
def query():
    """Query for input."""
    time.sleep(1)
    #1/0
    return "gpt"


@trace
def my_flow(input_val: str = "gpt") -> str:
    """Simple flow without yaml."""
    print("calling query")
    hello("world")
    #for i in range(3):
    #    query()
    stream_output = stream()
    print("type of stream_output:", type(stream_output))
    result = ", ".join(stream_output)
    return f"Hello world! {result} {input_val}"


if __name__ == "__main__":
    my_flow()