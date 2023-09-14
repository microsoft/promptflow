# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------


from flask.testing import FlaskClient


class PFSOperations:

    RUN_URL_PREFIX = "/run/v1.0"

    def __init__(self, client: FlaskClient):
        self._client = client

    def heartbeat(self):
        return self._client.get("/heartbeat")

    def list(self):
        # TODO: add query parameters
        return self._client.get(f"{self.RUN_URL_PREFIX}/list")

    def get(self, name: str):
        return self._client.get(f"{self.RUN_URL_PREFIX}/{name}")

    def get_metadata(self, name: str):
        return self._client.get(f"{self.RUN_URL_PREFIX}/{name}/metadata")

    def get_detail(self, name: str):
        return self._client.get(f"{self.RUN_URL_PREFIX}/{name}/detail")
