# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import random

def my_flow(input_val: str = "gpt") -> str:
    if random.random() < 0.5:
        raise ValueError("Random failure")
    return f"Hello world! {input_val}"
