# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from ._connection_provider import ConnectionProvider


class LocalConnectionProvider(ConnectionProvider):
    """Local connection provider."""

    def __init__(self):
        pass

    def get(self, name: str):
        pass
