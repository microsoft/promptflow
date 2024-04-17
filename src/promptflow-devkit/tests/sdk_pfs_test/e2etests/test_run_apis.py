# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json
import uuid
from dataclasses import fields
from pathlib import Path

import mock
import pytest

from promptflow._sdk.entities import Run
from promptflow._sdk.operations._local_storage_operations import LocalStorageOperations
from promptflow.client import PFClient
from promptflow.contracts._run_management import RunMetadata

from ..utils import PFSOperations, check_activity_end_telemetry

FLOW_PATH = "./tests/test_configs/flows/print_env_var"
DATA_PATH = "./tests/test_configs/datas/env_var_names.jsonl"


def create_run_against_multi_line_data(client: PFClient) -> Run:
    return client.run(flow=FLOW_PATH, data=DATA_PATH)


@pytest.mark.usefixtures("use_secrets_config_file")
@pytest.mark.e2etest
class TestRunAPIs:
    @pytest.fixture(autouse=True)
    def _submit_run(self, pf_client):
        self.run = create_run_against_multi_line_data(pf_client)

    def test_list_runs(self, pfs_op: PFSOperations) -> None:
        with check_activity_end_telemetry(activity_name="pf.runs.list"):
            response = pfs_op.list_runs(status_code=200).json
        assert len(response) >= 1

    @pytest.mark.skip(reason="Task 2917711: cli command will give strange stdout in ci; re-enable after switch to sdk")
    def test_submit_run(self, pfs_op: PFSOperations) -> None:
        # run submit is done via cli, so no telemetry will be detected here
        with check_activity_end_telemetry(expected_activities=[]):
            response = pfs_op.submit_run(
                {
                    "flow": Path(FLOW_PATH).absolute().as_posix(),
                    "data": Path(DATA_PATH).absolute().as_posix(),
                },
                status_code=200,
            )
        with check_activity_end_telemetry(activity_name="pf.runs.get"):
            run_from_pfs = pfs_op.get_run(name=response.json["name"]).json
        assert run_from_pfs

    def update_run(self, pfs_op: PFSOperations) -> None:
        display_name = "new_display_name"
        tags = {"key": "value"}
        with check_activity_end_telemetry(activity_name="pf.runs.update"):
            run_from_pfs = pfs_op.update_run(
                name=self.run.name, display_name=display_name, tags=json.dumps(tags), status_code=200
            ).json
        assert run_from_pfs["display_name"] == display_name
        assert run_from_pfs["tags"] == tags

    def test_archive_restore_run(self, pf_client: PFClient, pfs_op: PFSOperations) -> None:
        run = create_run_against_multi_line_data(pf_client)
        with check_activity_end_telemetry(
            expected_activities=[
                {"activity_name": "pf.runs.get", "first_call": False},
                {"activity_name": "pf.runs.archive"},
            ]
        ):
            pfs_op.archive_run(name=run.name, status_code=200)
        runs = pfs_op.list_runs().json
        assert not any([item["name"] == run.name for item in runs])
        with check_activity_end_telemetry(
            expected_activities=[
                {"activity_name": "pf.runs.get", "first_call": False},
                {"activity_name": "pf.runs.restore"},
            ]
        ):
            pfs_op.restore_run(name=run.name, status_code=200)
        runs = pfs_op.list_runs().json
        assert any([item["name"] == run.name for item in runs])

    def test_delete_run(self, pf_client: PFClient, pfs_op: PFSOperations) -> None:
        run = create_run_against_multi_line_data(pf_client)
        local_storage = LocalStorageOperations(run)
        path = local_storage.path
        assert path.exists()
        with check_activity_end_telemetry(
            expected_activities=[
                {"activity_name": "pf.runs.get", "first_call": False},
                {"activity_name": "pf.runs.delete"},
            ]
        ):
            pfs_op.delete_run(name=run.name, status_code=204)
        runs = pfs_op.list_runs().json
        assert not any([item["name"] == run.name for item in runs])
        assert not path.exists()

    def test_visualize_run(self, pfs_op: PFSOperations) -> None:
        with check_activity_end_telemetry(
            expected_activities=[
                {"activity_name": "pf.runs.get", "first_call": False},
                {"activity_name": "pf.runs.visualize"},
            ]
        ):
            response = pfs_op.get_run_visualize(name=self.run.name, status_code=200)
        assert response.data

    def test_get_not_exist_run(self, pfs_op: PFSOperations) -> None:
        random_name = str(uuid.uuid4())
        with check_activity_end_telemetry(activity_name="pf.runs.get", completion_status="Failure"):
            response = pfs_op.get_run(name=random_name)
        assert response.status_code == 404

    def test_get_run(self, pfs_op: PFSOperations) -> None:
        with check_activity_end_telemetry(activity_name="pf.runs.get"):
            run_from_pfs = pfs_op.get_run(name=self.run.name, status_code=200).json
        assert run_from_pfs["name"] == self.run.name

    def test_get_child_runs(self, pfs_op: PFSOperations) -> None:
        with check_activity_end_telemetry(activity_name="pf.runs.get"):
            run_from_pfs = pfs_op.get_child_runs(name=self.run.name, status_code=200).json
        assert len(run_from_pfs) == 1
        assert run_from_pfs[0]["parent_run_id"] == self.run.name

    def test_get_node_runs(self, pfs_op: PFSOperations) -> None:
        with check_activity_end_telemetry(activity_name="pf.runs.get"):
            run_from_pfs = pfs_op.get_node_runs(name=self.run.name, node_name="print_env", status_code=200).json
        assert len(run_from_pfs) == 1
        assert run_from_pfs[0]["node"] == "print_env"

    def test_get_run_log(self, pfs_op: PFSOperations, pf_client: PFClient) -> None:
        with check_activity_end_telemetry(activity_name="pf.runs.get"):
            log = pfs_op.get_run_log(name=self.run.name, status_code=200)
        assert not log.data.decode("utf-8").startswith('"')

    def test_get_run_metrics(self, pfs_op: PFSOperations) -> None:
        with check_activity_end_telemetry(activity_name="pf.runs.get"):
            metrics = pfs_op.get_run_metrics(name=self.run.name, status_code=200).json
        assert metrics is not None

        with check_activity_end_telemetry(activity_name="pf.runs.get"), mock.patch(
            "promptflow._sdk.operations._local_storage_operations.LocalStorageOperations.load_metrics"
        ) as mock_load_metrics:
            mock_load_metrics.side_effect = Exception("Not found metrics json")
            metrics = pfs_op.get_run_metrics(name=self.run.name, status_code=200).json
        assert metrics == {}

    def test_get_run_metadata(self, pfs_op: PFSOperations) -> None:
        with check_activity_end_telemetry(activity_name="pf.runs.get"):
            metadata = pfs_op.get_run_metadata(name=self.run.name, status_code=200).json
        for field in fields(RunMetadata):
            assert field.name in metadata
        assert metadata["name"] == self.run.name
