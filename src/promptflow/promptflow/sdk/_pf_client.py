# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from promptflow.sdk.operations import RunOperations
from promptflow.sdk.operations._connection_operations import ConnectionOperations


class PFClient:
    """A client class to interact with prompt flow entities."""

    def __init__(self):
        self._runs = RunOperations()
        self._connections = ConnectionOperations()

    @property
    def runs(self) -> RunOperations:
        return self._runs

    @property
    def connections(self) -> ConnectionOperations:
        return self._connections
