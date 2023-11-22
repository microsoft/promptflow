# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import getpass

from flask.testing import FlaskClient


class PFSOperations:

    CONNECTION_URL_PREFIX = "/v1.0/Connections"
    RUN_URL_PREFIX = "/v1.0/Runs"

    def __init__(self, client: FlaskClient):
        self._client = client

    def remote_user_header(self):
        return {"X-Remote-User": getpass.getuser()}

    def heartbeat(self):
        return self._client.get("/heartbeat")

    # connection APIs
    def connection_operation_with_invalid_user(self):
        return self._client.get(f"{self.CONNECTION_URL_PREFIX}/", headers={"X-Remote-User": "invalid_user"})

    def list_connections(self):
        return self._client.get(f"{self.CONNECTION_URL_PREFIX}/", headers=self.remote_user_header())

    def get_connection(self, name: str):
        return self._client.get(f"{self.CONNECTION_URL_PREFIX}/{name}", headers=self.remote_user_header())

    # run APIs
    def list_runs(self):
        # TODO: add query parameters
        return self._client.get(f"{self.RUN_URL_PREFIX}/", headers=self.remote_user_header())

    def get_run(self, name: str):
        return self._client.get(f"{self.RUN_URL_PREFIX}/{name}", headers=self.remote_user_header())

    def get_run_metadata(self, name: str):
        return self._client.get(f"{self.RUN_URL_PREFIX}/{name}/metadata", headers=self.remote_user_header())

    def get_run_detail(self, name: str):
        return self._client.get(f"{self.RUN_URL_PREFIX}/{name}/detail", headers=self.remote_user_header())
