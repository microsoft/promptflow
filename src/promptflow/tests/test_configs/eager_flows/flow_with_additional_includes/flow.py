# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
def my_flow_entry(input_val: str = "gpt") -> str:
    """Simple flow without yaml."""
    from entry import my_flow
    return my_flow(input_val=input_val)
