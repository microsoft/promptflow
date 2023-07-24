# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from typing import Union, List

from pandas import DataFrame

from promptflow.sdk.entities import Run

def stream(run: Union[str, Run]) -> None:
    """Stream run logs to the console.

    :param run: Run object or name of the run.
    :type run: Union[str, ~promptflow.sdk.entities.Run]
    """
    client = _get_azure_pf_client()
    if isinstance(run, Run):
        run = run.name
    client.runs.stream(run)


def get_details(run: Union[str, Run]) -> DataFrame:
    """Preview run inputs and outputs.

    :param run: Run object or name of the run.
    :type run: Union[str, ~promptflow.sdk.entities.Run]
    :return: The run's details
    :rtype: pandas.DataFrame
    """
    client = _get_azure_pf_client()
    if isinstance(run, Run):
        run = run.name
    return client.runs.get_details(run=run)


def get_metrics(run: Union[str, Run]) -> dict:
    """Print run metrics to the console.

    :param run: Run object or name of the run.
    :type run: Union[str, ~promptflow.sdk.entities.Run]
    :return: The run's metrics
    :rtype: dict
    """
    client = _get_azure_pf_client()
    if isinstance(run, Run):
        run = run.name
    return client.runs.get_metrics(run=run)


def visualize(runs: Union[List[str], List[Run]]) -> None:
    """Visualize run(s).

    :param run: Run object or name of the run.
    :type run: Union[str, ~promptflow.sdk.entities.Run]
    """
    client = _get_azure_pf_client()
    client.runs.visualize(runs)


def _get_azure_pf_client():
    from promptflow.azure._configuration import _CLIENT
    from promptflow.azure import PFClient
    if _CLIENT is None:
        raise ValueError("Please configure the MLClient first.")
    return PFClient(ml_client=_CLIENT)
