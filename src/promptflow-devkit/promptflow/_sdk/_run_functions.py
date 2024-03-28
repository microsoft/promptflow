# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from os import PathLike
from typing import IO, AnyStr, Union

from promptflow._sdk._load_functions import load_run
from promptflow._sdk._pf_client import PFClient
from promptflow._sdk.entities._run import Run


def _create_run(run: Run, **kwargs):
    client = PFClient()
    return client.runs.create_or_update(run=run, **kwargs)


def _resume_run(**kwargs):
    client = PFClient()
    # Pass through kwargs to run to ensure all params supported.
    return client.run(**kwargs)


def create_yaml_run(source: Union[str, PathLike, IO[AnyStr]], params_override: list = None, **kwargs):
    """Create a run from a yaml file. Should only call from CLI."""
    run = load_run(source, params_override=params_override, **kwargs)
    return _create_run(run=run, **kwargs)
