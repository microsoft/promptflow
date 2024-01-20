# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from promptflow import trace
import time


@trace
def hello(name):
    return f"Hello {name}"


@trace
def number(value):
    return value


@trace
def stream():
    for i in range(3):
        time.sleep(0.5)
        yield str(i)


@trace
def query():
    """Query for input."""
    time.sleep(1)
    #1/0
    return "gpt"


# How to add trace to a 3rd party function
traced_sum = trace(sum)


@trace
def my_flow(input_val: str = "gpt") -> str:
    """Simple flow without yaml."""
    print("calling query")
    hello("world")
    #for i in range(3):
    #    query()
    number(42)
    number(42.0)
    traced_sum((1, 2, 3))
    stream_output = stream()
    print("type of stream_output:", type(stream_output))
    result = ", ".join(stream_output)
    return {
        "greetings": f"Hello world! {input_val}",
        "stream_output": result,
    }


if __name__ == "__main__":
    my_flow()