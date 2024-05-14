# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from typing import TypedDict


class FlowOutput(TypedDict):
    func_input1: str
    func_input2: str



def my_flow(func_input1: str, func_input2: str) -> FlowOutput:
    return dict(func_input1=func_input1, func_input2=func_input2)
