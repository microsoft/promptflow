# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

def my_flow(input_val: str = "gpt") -> dict:
    """Simple flow without yaml."""
    return {"output": f"Hello world! {input_val}"}
