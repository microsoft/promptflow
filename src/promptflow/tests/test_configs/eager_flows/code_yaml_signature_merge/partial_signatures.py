# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from promptflow.tracing import trace


class MyFlow:
    def __init__(self, obj_input1: str, obj_input2: bool, obj_input3):
        self.obj_input1 = obj_input1
        self.obj_input2 = obj_input2
        self.obj_input3 = obj_input3

    @trace
    def __call__(self, func_input1: str, func_input2: int, func_input3):
        return func_input1


if __name__ == "__main__":
    flow = MyFlow("obj_input", True, 3.14)
    result = flow("func_input", 1, 3.14)
    print(result)

