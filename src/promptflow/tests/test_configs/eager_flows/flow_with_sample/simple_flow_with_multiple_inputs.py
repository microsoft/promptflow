# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from typing import TypedDict


class FlowOutput(TypedDict):
    obj_input1: str
    func_input1: str
    obj_input2: str
    func_input2: str


class MyFlow:
    def __init__(self, obj_input1: str, obj_input2: str):
        self.obj_input1 = obj_input1
        self.obj_input2 = obj_input2

    def __call__(self, func_input1: str, func_input2: str) -> FlowOutput:
        return dict(obj_input1=self.obj_input1, obj_input2=self.obj_input2, func_input1=func_input1, func_input2=func_input2)
