# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json
import uuid
from dataclasses import fields

import pytest

from promptflow import PFClient
from promptflow._sdk.entities import Run
from promptflow.contracts._run_management import RunMetadata

from ..utils import PFSOperations

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
        response = pfs_op.list_runs(status_code=200).json
        assert len(response) >= 1

    def submit_run(self, pfs_op: PFSOperations) -> None:
        response = pfs_op.submit_run({"flow": FLOW_PATH, "data": DATA_PATH}, status_code=200)
        run_from_pfs = pfs_op.get_run(name=response.json["name"]).json
        assert run_from_pfs

    def update_run(self, pfs_op: PFSOperations) -> None:
        display_name = "new_display_name"
        tags = {"key": "value"}
        run_from_pfs = pfs_op.update_run(
            name=self.run.name, display_name=display_name, tags=json.dumps(tags), status_code=200
        ).json
        assert run_from_pfs["display_name"] == display_name
        assert run_from_pfs["tags"] == tags

    def test_archive_restore_run(self, pf_client: PFClient, pfs_op: PFSOperations) -> None:
        run = create_run_against_multi_line_data(pf_client)
        pfs_op.archive_run(name=run.name, status_code=200)
        runs = pfs_op.list_runs().json
        assert not any([item["name"] == run.name for item in runs])
        pfs_op.restore_run(name=run.name, status_code=200)
        runs = pfs_op.list_runs().json
        assert any([item["name"] == run.name for item in runs])

    def test_visualize_run(self, pfs_op: PFSOperations) -> None:
        response = pfs_op.get_run_visualize(name=self.run.name, status_code=200)
        assert response.data

    def test_get_not_exist_run(self, pfs_op: PFSOperations) -> None:
        random_name = str(uuid.uuid4())
        response = pfs_op.get_run(name=random_name)
        assert response.status_code == 404

    def test_get_run(self, pfs_op: PFSOperations) -> None:
        run_from_pfs = pfs_op.get_run(name=self.run.name, status_code=200).json
        assert run_from_pfs["name"] == self.run.name

    def test_get_child_runs(self, pfs_op: PFSOperations) -> None:
        run_from_pfs = pfs_op.get_child_runs(name=self.run.name, status_code=200).json
        assert len(run_from_pfs) == 1
        assert run_from_pfs[0]["parent_run_id"] == self.run.name

    def test_get_node_runs(self, pfs_op: PFSOperations) -> None:
        run_from_pfs = pfs_op.get_node_runs(name=self.run.name, node_name="print_env", status_code=200).json
        assert len(run_from_pfs) == 1
        assert run_from_pfs[0]["node"] == "print_env"

    def test_get_run_log(self, pfs_op: PFSOperations, pf_client: PFClient) -> None:
        log = pfs_op.get_run_log(name=self.run.name, status_code=200)
        assert not log.data.decode("utf-8").startswith("\"")

    def test_get_run_metrics(self, pfs_op: PFSOperations) -> None:
        metrics = pfs_op.get_run_metrics(name=self.run.name, status_code=200).json
        assert metrics is not None

    def test_get_run_metadata(self, pfs_op: PFSOperations) -> None:
        metadata = pfs_op.get_run_metadata(name=self.run.name, status_code=200).json
        for field in fields(RunMetadata):
            assert field.name in metadata
        assert metadata["name"] == self.run.name
