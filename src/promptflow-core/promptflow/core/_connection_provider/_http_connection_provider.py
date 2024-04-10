# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from typing import Any

import httpx

from ._connection_provider import ConnectionProvider
from ._dict_connection_provider import DictConnectionProvider


class HttpConnectionProvider(ConnectionProvider):
    ENDPOINT_KEY = "PF_HTTP_CONNECTION_PROVIDER_ENDPOINT"
    """Connection provider based on http, core scenario: cloud submission."""

    def __init__(self, endpoint: str):
        self._endpoint = endpoint

    def get(self, name: str, **kwargs) -> Any:
        resp = httpx.get(f"{self._endpoint}/connections/{name}")
        resp.raise_for_status()  # TODO: Better error handling
        return DictConnectionProvider._build_connection(resp.json())

    def list(self) -> Any:
        resp = httpx.get(f"{self._endpoint}/connections")
        resp.raise_for_status()  # TODO: Better error handling
        return [DictConnectionProvider._build_connection((connection_dict)) for connection_dict in resp.json()]
