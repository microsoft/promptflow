# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from typing import Callable

import inspect
import json
import os
import tempfile

from promptflow.client import PFClient


def load_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f.readlines()]


def save_function_as_flow(fun: Callable, target_dir: str, pf: PFClient) -> None:
    """
    Save the function to the designated folder.

    :keyword fun: The function to be saved as a flow.
    :paramtype fun: Callable
    :keyword target_dir: The directory to save flow to.
    :paramtype target_dir: str
    :keyword pf: The promptflow client to be used for saving function.
    :paramtype: PFClient
    """
    if not os.path.isfile(inspect.getfile(fun)):
        # Handle the situation when the function is in the notebook.
        # In this case we cannot copy it using PFClient as the file
        # does not exist. We will do our best to save the file, however
        # in this case function may miss required imports.
        lines = inspect.getsource(fun)
        os.makedirs(target_dir, exist_ok=True)
        source = tempfile.TemporaryFile(suffix='.py', mode='w', delete=False)
        source.write(lines)
        source.close()
        try:
            pf.flows.save(
                entry=fun.__name__,
                code=source.name,
                path=target_dir
            )
        finally:
            os.unlink(source.name)
    else:
        pf.flows.save(
            entry=fun,
            path=target_dir
        )
