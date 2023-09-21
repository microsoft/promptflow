# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------


from flask.testing import FlaskClient


class PFSOperations:

    CONNECTION_URL_PREFIX = "/connection/v1.0"
    RUN_URL_PREFIX = "/run/v1.0"

    def __init__(self, client: FlaskClient):
        self._client = client

    def heartbeat(self):
        return self._client.get("/heartbeat")

    # connection APIs
    def list_connections(self):
        return self._client.get(f"{self.CONNECTION_URL_PREFIX}/list")

    def get_connection(self, name: str):
        return self._client.get(f"{self.CONNECTION_URL_PREFIX}/{name}")

    # run APIs
    def list_runs(self):
        # TODO: add query parameters
        return self._client.get(f"{self.RUN_URL_PREFIX}/list")

    def get_run(self, name: str):
        return self._client.get(f"{self.RUN_URL_PREFIX}/{name}")

    def get_run_metadata(self, name: str):
        return self._client.get(f"{self.RUN_URL_PREFIX}/{name}/metadata")

    def get_run_detail(self, name: str):
        return self._client.get(f"{self.RUN_URL_PREFIX}/{name}/detail")
