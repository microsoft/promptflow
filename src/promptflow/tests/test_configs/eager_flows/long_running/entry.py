# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import time


def my_flow(input_val) -> str:
    """Simple flow with yaml."""
    time.sleep(100)
    print(f"Hello world! {input_val}")
    return f"Hello world! {input_val}"
