# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import time
def my_flow(input_val: str = "gpt") -> str:
    for c in "Hello world! ":
        time.sleep(1)
        yield c
