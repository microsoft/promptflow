# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from promptflow import trace
import time


@trace
def query():
    """Query for input."""
    time.sleep(1)
    return "gpt"


def my_flow(input_val: str = "gpt") -> str:
    """Simple flow without yaml."""
    query()
    return f"Hello world! {input_val}"
