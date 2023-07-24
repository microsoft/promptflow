# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import os
import uuid
from os import PathLike
from pathlib import Path
from typing import Union

from promptflow.azure._configuration import _get_run_operations
from promptflow.sdk.entities import Run


def _create_run(run: Run, **kwargs):
    run_ops = _get_run_operations()
    return run_ops.create_or_update(run=run, **kwargs)


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
