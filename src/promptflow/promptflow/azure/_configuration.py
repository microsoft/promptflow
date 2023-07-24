# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import logging

from ._ml import MLClient


_CLIENT = None
_RUNTIME = None

logger = logging.getLogger(__name__)


def configure(client: MLClient, **kwargs):
    """Configure the MLClient with the runtime and the default flow.

    Args:
        client (MLClient): The MLClient to configure.
        runtime (str): The runtime to use.
    """
    global _CLIENT, _RUNTIME
    _CLIENT = client
    _RUNTIME = kwargs.get("runtime", None)
    logger.info(f"Configured MLClient {_CLIENT} with runtime {_RUNTIME}")



def _get_flow_operations():
    from .operations import FlowOperations

    if _CLIENT is None:
        raise ValueError("Please configure the MLClient first.")

    flow_operations = FlowOperations(
        operation_scope=_CLIENT._operation_scope,
        operation_config=_CLIENT._operation_config,
        all_operations=_CLIENT._operation_container,
        credential=_CLIENT._credential
    )
    return flow_operations


def _get_flow_job_operations():
    from .operations._flow_job_operations import FlowJobOperations

    flow_run_operations = FlowJobOperations(
        operation_scope=_CLIENT._operation_scope,
        operation_config=_CLIENT._operation_config,
        all_operations=_CLIENT._operation_container,
        credential=_CLIENT._credential
    )
    return flow_run_operations


def _get_connection_operations():
    from .operations import ConnectionOperations

    connection_operations = ConnectionOperations(
        operation_scope=_CLIENT._operation_scope,
        operation_config=_CLIENT._operation_config,
        all_operations=_CLIENT._operation_container,
        credential=_CLIENT._credential
    )
    return connection_operations


def _get_run_operations():
    from . import PFClient

    if _CLIENT is None:
        raise ValueError("Please configure the MLClient first.")

    client = PFClient(_CLIENT)
    return client.runs


def _get_ml_client():
    if _CLIENT is None:
        raise ValueError("Please configure the MLClient first.")
    return _CLIENT
