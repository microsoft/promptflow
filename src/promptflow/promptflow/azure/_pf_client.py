# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import json

from azure.ai.ml import MLClient
from typing import Union, List
from promptflow.sdk._constants import ListViewType
from promptflow.sdk.entities import Run
from promptflow.azure.operations import RunOperations, FlowOperations


class PFClient:
    """A client class to interact with Promptflow service.

    Use this client to manage promptflow resources, e.g. runs

    :param ml_client: An instance of MLClient, indicates to interact with Promptflow service
    :type ml_client: azure.ai.ml.entities.MLClient
    """

    def __init__(self, ml_client):
        if not isinstance(ml_client, MLClient):
            raise ValueError(f"ml_client must be an instance of 'azure.ai.MLClient', got {type(ml_client)!r} instead.")
        self._client = ml_client
        self._flows = FlowOperations(
            operation_scope=ml_client._operation_scope,
            operation_config=ml_client._operation_config,
            all_operations=ml_client._operation_container,
            credential=ml_client._credential
        )
        self._runs = RunOperations(
            operation_scope=ml_client._operation_scope,
            operation_config=ml_client._operation_config,
            all_operations=ml_client._operation_container,
            credential=ml_client._credential,
            flow_operations=self._flows,
        )

    @property
    def runs(self):
        return self._runs
