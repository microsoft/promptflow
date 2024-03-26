# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from promptflow.core._connection_provider._connection_provider import ConnectionProvider


class LocalConnectionProvider(ConnectionProvider):
    """Local connection provider."""

    def __init__(self):
        from promptflow._sdk.operations._connection_operations import ConnectionOperations

        self._operations = ConnectionOperations()

    def get(self, name: str, **kwargs):
        return self._operations.get(name, **kwargs)
