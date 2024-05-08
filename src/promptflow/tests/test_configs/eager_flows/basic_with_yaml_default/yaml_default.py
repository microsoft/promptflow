# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from dataclasses import dataclass

from promptflow.tracing import trace


class MyFlow:
    def __init__(self, obj_input: str = "code_default"):
        self.obj_input = obj_input

    @trace
    def __call__(self, func_input1: str, func_input2: str = "code_default") -> str:
        return "_".join([self.obj_input, func_input1, func_input2])

    def __aggregate__(self, results: list) -> dict:

        return {"length": len(results)}


if __name__ == "__main__":
    flow = MyFlow("obj_input")
    result = flow("func_input")
    print(result)

