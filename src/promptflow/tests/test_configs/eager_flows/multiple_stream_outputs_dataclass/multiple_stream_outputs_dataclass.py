# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from dataclasses import dataclass

@dataclass
class MyOutput:
    output1: str
    output2: str


def my_flow(input_val: str = "gpt") -> MyOutput:
    generator1 = (i for i in range(10))
    generator2 = (i for i in range(10))
    return MyOutput(
        output1=generator1,
        output2=generator2,
    )
