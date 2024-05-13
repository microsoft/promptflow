# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from typing import TypedDict

from promptflow.tracing import trace


class FlowOutput(TypedDict):
    str_output: str
    bool_output: bool
    int_output: int
    float_output: float


class MyFlow:
    def __init__(self, obj_input: str):
        self.obj_input = obj_input

    @trace
    def __call__(self, str_input: str, bool_input: bool, int_input: int, float_input: float) -> FlowOutput:
        return {
            "str_output": str_input,
            "bool_output": not bool_input,
            "int_output": int_input + 1,
            "float_output": float_input + 1.0,
        }
