# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import contextlib
import getpass
import json
from typing import Any, Dict, List, Optional
from unittest import mock

import werkzeug
from flask.testing import FlaskClient


@contextlib.contextmanager
def check_activity_end_telemetry(
    *,
    expected_activities: List[Dict[str, Any]] = None,
    **kwargs,
):
    if expected_activities is None and kwargs:
        expected_activities = [kwargs]
    with mock.patch("promptflow._sdk._telemetry.activity.log_activity_end") as mock_telemetry:
        yield
        actual_activities = [call.args[0] for call in mock_telemetry.call_args_list]
        assert mock_telemetry.call_count == len(expected_activities), (
            f"telemetry should not be called {len(expected_activities)} times but got {mock_telemetry.call_count}:\n"
            f"{json.dumps(actual_activities, indent=2)}\n"
        )

        default_expected_call = {
            "first_call": True,
            "activity_type": "PublicApi",
            "completion_status": "Success",
            "user_agent": f"promptflow-sdk/0.0.1 Werkzeug/{werkzeug.__version__} local_pfs/0.0.1",
        }
        for i, expected_activity in enumerate(expected_activities):
            temp = default_expected_call.copy()
            temp.update(expected_activity)
            expected_activity = temp
            for key, expected_value in expected_activity.items():
                value = actual_activities[i][key]
                assert (
                    value == expected_value
                ), f"{key} mismatch in {i+1}th call: expect {expected_value} but got {value}"


class PFSOperations:

    CONNECTION_URL_PREFIX = "/v1.0/Connections"
    RUN_URL_PREFIX = "/v1.0/Runs"
    TELEMETRY_PREFIX = "/v1.0/Telemetries"
    LINE_RUNS_PREFIX = "/v1.0/LineRuns"

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

    def delete_connection(self, name: str, status_code=None):
        response = self._client.delete(f"{self.CONNECTION_URL_PREFIX}/{name}", headers=self.remote_user_header())
        if status_code:
            assert status_code == response.status_code, response.text
        return response

    def list_connections_by_provider(self, working_dir, status_code=None):
        response = self._client.get(
            f"{self.CONNECTION_URL_PREFIX}/",
            query_string={"working_directory": working_dir},
            headers=self.remote_user_header(),
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
        response = self._client.post(f"{self.RUN_URL_PREFIX}/submit", json=request_body)
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
        response = self._client.put(f"{self.RUN_URL_PREFIX}/{name}", json=request_body)
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

    def delete_run(self, name: str, status_code=None):
        response = self._client.delete(f"{self.RUN_URL_PREFIX}/{name}")
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

    # telemetry APIs
    def create_telemetry(self, *, body, headers, status_code=None):
        response = self._client.post(
            f"{self.TELEMETRY_PREFIX}/",
            headers={
                **self.remote_user_header(),
                **headers,
            },
            json=body,
        )
        if status_code:
            assert status_code == response.status_code, response.text
        return response

    # trace APIs
    # LineRuns
    def list_line_runs(self, *, session_id: Optional[str] = None, runs: Optional[List[str]] = None):
        query_string = {}
        if session_id is not None:
            query_string["session"] = session_id
        if runs is not None:
            query_string["run"] = ",".join(runs)
        response = self._client.get(
            f"{self.LINE_RUNS_PREFIX}/list",
            query_string=query_string,
            headers=self.remote_user_header(),
        )
        return response
