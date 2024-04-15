# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from typing import TypedDict


def my_flow(input_val: str = "gpt") -> TypedDict("MyFlowResult", {"output": str}):
    """Simple flow without yaml."""
    return {"output": f"Hello world! {input_val}"}
