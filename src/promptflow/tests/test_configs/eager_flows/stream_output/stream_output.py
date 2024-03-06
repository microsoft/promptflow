# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

def my_flow(input_val: str = "gpt") -> str:
    for c in "Hello world! ":
        yield c
