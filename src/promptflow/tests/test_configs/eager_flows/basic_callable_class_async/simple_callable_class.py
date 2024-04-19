# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import asyncio
from typing import TypedDict

class FlowOutput(TypedDict):
    obj_input: str
    func_input: str
    obj_id: str


class MyFlow:
    def __init__(self, obj_input: str):
        self.obj_input = obj_input

    async def __call__(self, func_input: str) -> FlowOutput:
        await asyncio.sleep(1)
        return {
            "obj_input": self.obj_input,
            "func_input": func_input,
            "obj_id": id(self),
        }

    async def __aggregate__(self, results: list) -> dict:
        await asyncio.sleep(1)
        return {"length": len(results)}


if __name__ == "__main__":
    flow = MyFlow("obj_input")
    result = flow("func_input")
    print(result)

