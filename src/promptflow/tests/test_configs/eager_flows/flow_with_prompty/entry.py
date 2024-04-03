# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from pathlib import Path
from promptflow.core._flow import Prompty


def my_flow(input_val) -> str:
    """Simple flow with yaml."""

    prompty_node = Prompty.load(source="hello.prompty")
    result = prompty_node(text=input_val)
    print(f"Hello world! {result}")
    return f"Hello world! {result}"
