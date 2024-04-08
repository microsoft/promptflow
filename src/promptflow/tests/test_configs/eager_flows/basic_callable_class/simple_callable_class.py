# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from promptflow.core import log_metric

class MyFlow:
    def __init__(self, obj_input: str):
        self.obj_input = obj_input

    def __call__(self, func_input: str) -> dict:
        return {
            "obj_input": self.obj_input,
            "func_input": func_input,
            "obj_id": id(self),
        }

    def __aggregate__(self, results: list) -> dict:
        log_metric("length", len(results))
        return results


if __name__ == "__main__":
    flow = MyFlow("obj_input")
    result = flow("func_input")
    print(result)

