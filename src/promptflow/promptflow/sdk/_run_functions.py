# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import os.path
import uuid
from os import PathLike
from pathlib import Path
from typing import IO, Any, AnyStr, Dict, List, Union

import pandas as pd

from promptflow.sdk._load_functions import load_run
from promptflow.sdk._pf_client import PFClient
from promptflow.sdk.entities._run import Run


def _create_run(run: Run, **kwargs):
    client = PFClient()
    return client.runs.create_or_update(run=run, **kwargs)


def run(
    flow: Union[str, PathLike],
    *,
    data: Union[str, PathLike] = None,
    run: Union[str, Run] = None,
    column_mapping: dict = None,
    variant: str = None,
    **kwargs,
) -> Run:
    """Run flow against provided data or run.
    Note: at least one of data or run must be provided.

    :param flow: path to flow directory to run evaluation
    :param data: pointer to test data (of variant bulk runs) for eval runs
    :param run:
        flow run id or flow run
        keep lineage between current run and variant runs
        batch outputs can be referenced as ${run.outputs.col_name} in inputs_mapping
    :param column_mapping: define a data flow logic to map input data, support:
        from data: data.col1:
        from variant:
            [0].col1, [1].col2: if need different col from variant run data
            variant.output.col1: if all upstream runs has col1
        Example:
            {"ground_truth": "${data.answer}", "prediction": "${run.outputs.answer}"}
    :param variant: Node & variant name in format of ${node_name.variant_name}, will use default variant
        if not specified.
    :return: flow run info.
    """
    if not os.path.exists(flow):
        raise FileNotFoundError(f"flow path {flow} does not exist")
    if data and not os.path.exists(data):
        raise FileNotFoundError(f"data path {data} does not exist")
    if not run and not data:
        raise ValueError("at least one of data or run must be provided")

    run = Run(
        # TODO(2523341): default to flow folder name + timestamp
        name=str(uuid.uuid4()),
        data=data,
        column_mapping=column_mapping,
        run=run,
        variant=variant,
        flow=Path(flow),
    )
    return _create_run(run=run, **kwargs)


def create_yaml_run(source: Union[str, PathLike, IO[AnyStr]], params_override: list = None, **kwargs):
    """Create a run from a yaml file. Should only call from CLI."""
    run = load_run(source, params_override=params_override, **kwargs)
    return _create_run(run=run, **kwargs)


def stream(run: Union[str, Run]) -> None:
    """Stream run logs to the console.

    :param run: Run object or name of the run.
    :type run: Union[str, ~promptflow.sdk.entities.Run]
    """
    client = PFClient()
    client.runs.stream(run)


def get_details(run: Union[str, Run]) -> pd.DataFrame:
    """Get run inputs and outputs.

    :param run: Run object or name of the run.
    :type run: Union[str, ~promptflow.sdk.entities.Run]
    :return: Run details.
    :rtype: ~pandas.DataFrame
    """
    client = PFClient()
    return client.runs.get_details(run)


def get_metrics(run: Union[str, Run]) -> Dict[str, Any]:
    """Get run metrics.

    :param run: Run object or name of the run.
    :type run: Union[str, ~promptflow.sdk.entities.Run]
    :return: Run metrics.
    :rtype: Dict[str, Any]
    """
    client = PFClient()
    return client.runs.get_metrics(run)


def visualize(runs: Union[List[str], List[Run]]) -> None:
    """Visualize run(s).

    :param run: Run object or name of the run.
    :type run: Union[str, ~promptflow.sdk.entities.Run]
    """
    client = PFClient()
    client.runs.visualize(runs)
