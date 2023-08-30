# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from typing import List

from flask.testing import FlaskClient


class PFSOperations:

    RUN_URL_PREFIX = "/run/v1.0"

    def __init__(self, client: FlaskClient):
        self._client = client

    def heartbeat(self):
        return self._client.get("/heartbeat")

    def list(self) -> List[dict]:
        # TODO: add query parameters
        return self._client.get(f"{self.RUN_URL_PREFIX}/list")

    def get(self, name: str) -> dict:
        return self._client.get(f"{self.RUN_URL_PREFIX}/{name}").json

    def get_metadata(self, name: str) -> dict:
        return self._client.get(f"{self.RUN_URL_PREFIX}/{name}/metadata").json

    def get_detail(self, name: str) -> dict:
        return self._client.get(f"{self.RUN_URL_PREFIX}/{name}/detail").json
