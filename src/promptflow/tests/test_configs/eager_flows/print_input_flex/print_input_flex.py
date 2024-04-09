# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import sys

def my_flow(text: str) -> str:
    """Simple flow without yaml."""
    print(f"Hello flex {text}")
    print(f"Hello error {text}", file=sys.stderr)
    return f"Hello world! {text}"
