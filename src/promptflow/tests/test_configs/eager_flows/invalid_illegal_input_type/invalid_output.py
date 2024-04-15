# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from typing import TypedDict


class FlowOutput(TypedDict):
    obj_input: object
    func_input: str
    obj_id: str


class MyFlow:
    def __init__(self, obj_input: str):
        self.obj_input = obj_input

    def __call__(self, func_input: str) -> FlowOutput:
        pass


if __name__ == "__main__":
    flow = MyFlow("obj_input")
    result = flow("func_input")
    print(result)

