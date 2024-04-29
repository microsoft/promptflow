# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from dataclasses import dataclass

from promptflow.tracing import trace

@dataclass
class FlowOutput:
    obj_input: str
    func_input: str
    obj_id: str


class MyFlow:
    def __init__(self, obj_input: str):
        self.obj_input = obj_input

    @trace
    def __call__(self, func_input: str) -> FlowOutput:
        return FlowOutput(obj_input=self.obj_input, func_input=func_input, obj_id=id(self))

    def __aggregate__(self, results: list) -> dict:
        # Try attribute-style access for the datacalss
        obj_inputs = [r.obj_input for r in results]
        func_inputs = [r.func_input for r in results]
        obj_ids = [r.obj_id for r in results]

        return {"length": len(results)}


if __name__ == "__main__":
    flow = MyFlow("obj_input")
    result = flow("func_input")
    print(result)

