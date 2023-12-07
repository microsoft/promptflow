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
    def connection_operation_with_invalid_user(self, status_code=None):
        response = self._client.get(f"{self.CONNECTION_URL_PREFIX}/", headers={"X-Remote-User": "invalid_user"})
        if status_code:
            assert status_code == response.status_code, response.text
        return response

    def list_connections(self, status_code=None):
        response = self._client.get(f"{self.CONNECTION_URL_PREFIX}/", headers=self.remote_user_header())
        if status_code:
            assert status_code == response.status_code, response.text
        return response

    def list_connections_by_provider(self, working_dir, status_code=None):
        response = self._client.get(
            f"{self.CONNECTION_URL_PREFIX}/", data={"working_directory": working_dir}, headers=self.remote_user_header()
        )
        if status_code:
            assert status_code == response.status_code, response.text
        return response

    def get_connection(self, name: str, status_code=None):
        response = self._client.get(f"{self.CONNECTION_URL_PREFIX}/{name}", headers=self.remote_user_header())
        if status_code:
            assert status_code == response.status_code, response.text
        return response

    def get_connections_by_provider(self, name: str, working_dir, status_code=None):
        response = self._client.get(
            f"{self.CONNECTION_URL_PREFIX}/{name}",
            query_string={"working_directory": working_dir},
            headers=self.remote_user_header(),
        )
        if status_code:
            assert status_code == response.status_code, response.text
        return response

    def get_connection_with_secret(self, name: str, status_code=None):
        response = self._client.get(
            f"{self.CONNECTION_URL_PREFIX}/{name}/listsecrets", headers=self.remote_user_header()
        )
        if status_code:
            assert status_code == response.status_code, response.text
        return response

    def get_connection_specs(self, status_code=None):
        response = self._client.get(f"{self.CONNECTION_URL_PREFIX}/specs")
        if status_code:
            assert status_code == response.status_code, response.text
        return response

    # run APIs
    def list_runs(self, status_code=None):
        # TODO: add query parameters
        response = self._client.get(f"{self.RUN_URL_PREFIX}/", headers=self.remote_user_header())
        if status_code:
            assert status_code == response.status_code, response.text
        return response

    def submit_run(self, request_body, status_code=None):
        response = self._client.post(f"{self.RUN_URL_PREFIX}/", json=request_body)
        if status_code:
            assert status_code == response.status_code, response.text
        return response

    def update_run(
        self, name: str, display_name: str = None, description: str = None, tags: str = None, status_code=None
    ):
        request_body = {
            "display_name": display_name,
            "description": description,
            "tags": tags,
        }
        response = self._client.get(f"{self.RUN_URL_PREFIX}/{name}", json=request_body)
        if status_code:
            assert status_code == response.status_code, response.text
        return response

    def archive_run(self, name: str, status_code=None):
        response = self._client.get(f"{self.RUN_URL_PREFIX}/{name}/archive")
        if status_code:
            assert status_code == response.status_code, response.text
        return response

    def restore_run(self, name: str, status_code=None):
        response = self._client.get(f"{self.RUN_URL_PREFIX}/{name}/restore")
        if status_code:
            assert status_code == response.status_code, response.text
        return response

    def get_run_visualize(self, name: str, status_code=None):
        response = self._client.get(f"{self.RUN_URL_PREFIX}/{name}/visualize")
        if status_code:
            assert status_code == response.status_code, response.text
        return response

    def get_run(self, name: str, status_code=None):
        response = self._client.get(f"{self.RUN_URL_PREFIX}/{name}")
        if status_code:
            assert status_code == response.status_code, response.text
        return response

    def get_child_runs(self, name: str, status_code=None):
        response = self._client.get(f"{self.RUN_URL_PREFIX}/{name}/childRuns")
        if status_code:
            assert status_code == response.status_code, response.text
        return response

    def get_node_runs(self, name: str, node_name: str, status_code=None):
        response = self._client.get(f"{self.RUN_URL_PREFIX}/{name}/nodeRuns/{node_name}")
        if status_code:
            assert status_code == response.status_code, response.text
        return response

    def get_run_metadata(self, name: str, status_code=None):
        response = self._client.get(f"{self.RUN_URL_PREFIX}/{name}/metaData")
        if status_code:
            assert status_code == response.status_code, response.text
        return response

    def get_run_log(self, name: str, status_code=None):
        response = self._client.get(f"{self.RUN_URL_PREFIX}/{name}/logContent")
        if status_code:
            assert status_code == response.status_code, response.text
        return response

    def get_run_metrics(self, name: str, status_code=None):
        response = self._client.get(f"{self.RUN_URL_PREFIX}/{name}/metrics")
        if status_code:
            assert status_code == response.status_code, response.text
        return response
