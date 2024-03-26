# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import os


def env_var_flow(key):
    """Simple flow without yaml."""
    return f"Hello world! {os.environ.get(key)}"
