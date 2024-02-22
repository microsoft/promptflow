# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import os


def my_flow():
    """Simple flow without yaml."""
    return f"Hello world! {os.environ.get('TEST')}"
