# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import logging

from ._ml import MLClient


_CLIENT = None
_RUNTIME = None
_PF_CLIENT = None

logger = logging.getLogger(__name__)


def configure(client: MLClient, **kwargs):
    """Configure the MLClient with the runtime and the default flow.

    Args:
        client (MLClient): The MLClient to configure.
        runtime (str): The runtime to use.
    """
    global _CLIENT, _RUNTIME, _PF_CLIENT
    _CLIENT = client
    _RUNTIME = kwargs.get("runtime", None)
    logger.info(f"Configured MLClient {_CLIENT} with runtime {_RUNTIME}")

    from . import PFClient

    _PF_CLIENT = PFClient(_CLIENT, **kwargs)


def _get_flow_operations():
    if _CLIENT is None or _PF_CLIENT is None:
        raise ValueError("Please configure the MLClient first.")
    return _PF_CLIENT._flows


def _get_connection_operations():
    if _CLIENT is None or _PF_CLIENT is None:
        raise ValueError("Please configure the MLClient first.")

    return _PF_CLIENT._connections


def _get_run_operations():
    if _CLIENT is None or _PF_CLIENT is None:
        raise ValueError("Please configure the MLClient first.")

    return _PF_CLIENT.runs


def _get_ml_client():
    if _CLIENT is None:
        raise ValueError("Please configure the MLClient first.")
    return _CLIENT
