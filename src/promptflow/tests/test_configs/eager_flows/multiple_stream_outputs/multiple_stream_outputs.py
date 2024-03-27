# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
def my_flow(input_val: str = "gpt") -> dict:
    generator1 = (i for i in range(10))
    generator2 = (i for i in range(10))
    return {
        "output1": generator1,
        "output2": generator2,
    }