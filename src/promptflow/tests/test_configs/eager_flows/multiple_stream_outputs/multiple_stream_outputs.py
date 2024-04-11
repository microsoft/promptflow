# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from typing import TypedDict


def my_flow(input_val: str = "gpt") -> TypedDict("MyFlowResult", {"output1": int, "output2": int}):
    generator1 = (i for i in range(10))
    generator2 = (i for i in range(10))
    return {
        "output1": generator1,
        "output2": generator2,
    }