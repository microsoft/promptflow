# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import contextlib
import getpass
import importlib.metadata
import json
from typing import Any, Dict, List, Optional
from unittest import mock

from flask.testing import FlaskClient

from promptflow._sdk._service.utils.utils import encrypt_flow_path
from promptflow._sdk._version import VERSION


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
            "user_agent": [f"Werkzeug/{importlib.metadata.version('werkzeug')}", f"local_pfs/{VERSION}"],
        }
        for i, expected_activity in enumerate(expected_activities):
            temp = default_expected_call.copy()
            temp.update(expected_activity)
            expected_activity = temp
            for key, expected_value in expected_activity.items():
                value = actual_activities[i][key]
                if isinstance(expected_value, list):
                    value = list(sorted(value.split(" ")))
                    expected_value = list(sorted(expected_value))
                assert (
                    value == expected_value
                ), f"{key} mismatch in {i+1}th call: expect {expected_value} but got {value}"


class PFSOperations:

    CONNECTION_URL_PREFIX = "/v1.0/Connections"
    RUN_URL_PREFIX = "/v1.0/Runs"
    TELEMETRY_PREFIX = "/v1.0/Telemetries"
    LINE_RUNS_PREFIX = "/v1.0/LineRuns"
    Flow_URL_PREFIX = "/v1.0/Flows"
    UI_URL_PREFIX = "/v1.0/ui"
    EXPERIMENT_PREFIX = "/v1.0/Experiments"

    def __init__(self, client: FlaskClient):
        self._client = client

    def remote_user_header(self, user_agent=None):
        if user_agent:
            return {
                "X-Remote-User": getpass.getuser(),
                "User-Agent": user_agent,
            }
        return {"X-Remote-User": getpass.getuser()}

    def heartbeat(self):
        return self._client.get("/heartbeat")

    def root_page(self):
        return self._client.get("/")

    # connection APIs
    def connection_operation_with_invalid_user(self, name, status_code=None):
        response = self._client.get(
            f"{self.CONNECTION_URL_PREFIX}/{name}/listsecrets", headers={"X-Remote-User": "invalid_user"}
        )
        if status_code:
            assert status_code == response.status_code, response.text
        return response

    def list_connections(self, status_code=None, user_agent=None):
        response = self._client.get(
            f"{self.CONNECTION_URL_PREFIX}/", headers=self.remote_user_header(user_agent=user_agent)
        )
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
    # LineRuns/list
    def list_line_runs(
        self,
        *,
        collection: Optional[str] = None,
        runs: Optional[List[str]] = None,
        trace_ids: Optional[List[str]] = None,
        session_id: Optional[str] = None,
        line_run_ids: Optional[List[str]] = None,
    ):
        query_string = {}
        if collection is not None:
            query_string["collection"] = collection
        if runs is not None:
            query_string["run"] = ",".join(runs)
        if trace_ids is not None:
            query_string["trace_ids"] = ",".join(trace_ids)
        if line_run_ids is not None:
            query_string["line_run_ids"] = ",".join(line_run_ids)
        if session_id is not None:
            query_string["session"] = session_id
        response = self._client.get(
            f"{self.LINE_RUNS_PREFIX}/list",
            query_string=query_string,
            headers=self.remote_user_header(),
        )
        return response

    # LineRuns/search
    def search_line_runs(
        self,
        *,
        expression: str,
        collection: Optional[str] = None,
        runs: Optional[List[str]] = None,
        session_id: Optional[str] = None,
    ):
        query_string = {"expression": expression}
        if collection is not None:
            query_string["collection"] = collection
        if runs is not None:
            query_string["run"] = ",".join(runs)
        if session_id is not None:
            query_string["session"] = session_id
        response = self._client.get(
            f"{self.LINE_RUNS_PREFIX}/search",
            query_string=query_string,
            headers=self.remote_user_header(),
        )
        return response

    # LineRuns/Collections/list
    def list_collections(
        self,
        *,
        limit: Optional[int] = None,
    ):
        query_string = {}
        if limit is not None:
            query_string["limit"] = limit
        response = self._client.get(
            f"{self.LINE_RUNS_PREFIX}/Collections/list",
            query_string=query_string,
            headers=self.remote_user_header(),
        )
        return response

    def get_flow_yaml(self, flow_path: str, status_code=None):
        flow_path = encrypt_flow_path(flow_path)
        query_string = {"flow": flow_path}
        response = self._client.get(f"{self.UI_URL_PREFIX}/yaml", query_string=query_string)
        if status_code:
            assert status_code == response.status_code, response.text
        return response

    def get_experiment_yaml(self, flow_path: str, experiment_path: str, status_code=None):
        flow_path = encrypt_flow_path(flow_path)
        query_string = {"flow": flow_path, "experiment": experiment_path}
        response = self._client.get(f"{self.UI_URL_PREFIX}/yaml", query_string=query_string)
        if status_code:
            assert status_code == response.status_code, response.text
        return response

    def test_flow(self, flow_path, request_body, status_code=None):
        flow_path = encrypt_flow_path(flow_path)
        query_string = {"flow": flow_path}
        response = self._client.post(f"{self.Flow_URL_PREFIX}/test", json=request_body, query_string=query_string)
        if status_code:
            assert status_code == response.status_code, response.text
        return response

    def test_flow_infer_signature(self, flow_path, include_primitive_output, status_code=None):
        flow_path = encrypt_flow_path(flow_path)
        query_string = {"source": flow_path, "include_primitive_output": include_primitive_output}
        response = self._client.post(f"{self.Flow_URL_PREFIX}/infer_signature", query_string=query_string)
        if status_code:
            assert status_code == response.status_code, response.text
        return response

    def get_flow_ux_inputs(self, flow_path: str, status_code=None):
        flow_path = encrypt_flow_path(flow_path)
        query_string = {"flow": flow_path}
        response = self._client.get(f"{self.UI_URL_PREFIX}/ux_inputs", query_string=query_string)
        if status_code:
            assert status_code == response.status_code, response.text
        return response

    def save_flow_image(self, flow_path: str, request_body, status_code=None):
        flow_path = encrypt_flow_path(flow_path)
        query_string = {"flow": flow_path}
        response = self._client.post(f"{self.UI_URL_PREFIX}/media_save", json=request_body, query_string=query_string)
        if status_code:
            assert status_code == response.status_code, response.text
        return response

    def show_image(self, flow_path: str, image_path: str, status_code=None):
        flow_path = encrypt_flow_path(flow_path)
        query_string = {"flow": flow_path, "image_path": image_path}
        response = self._client.get(f"{self.UI_URL_PREFIX}/media", query_string=query_string)
        if status_code:
            assert status_code == response.status_code, response.text
        return response

    # Experiment APIs
    def experiment_test(self, body: dict):
        response = self._client.post(
            f"{self.EXPERIMENT_PREFIX}/test_with_flow_override",
            json=body,
        )
        return response

    def experiment_test_with_skip(self, body: dict):
        response = self._client.post(
            f"{self.EXPERIMENT_PREFIX}/skip_test",
            json=body,
        )
        return response
