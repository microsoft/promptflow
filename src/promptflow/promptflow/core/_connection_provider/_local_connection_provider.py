# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from .._errors import MissingRequiredPackage
from ._connection_provider import ConnectionProvider


class LocalConnectionProvider(ConnectionProvider):
    """Local connection provider."""

    def __init__(self):
        try:
            from promptflow._sdk.operations._connection_operations import ConnectionOperations
        except ImportError as e:
            raise MissingRequiredPackage(message="Please install 'promptflow-devkit' to use local connection.") from e
        self._operations = ConnectionOperations()

    def get(self, name: str, **kwargs):
        return self._operations.get(name, **kwargs)
