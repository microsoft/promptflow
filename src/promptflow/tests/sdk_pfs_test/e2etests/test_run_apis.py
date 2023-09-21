# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import uuid
from dataclasses import fields

import pytest

from promptflow import PFClient
from promptflow._sdk.entities import Run
from promptflow._sdk.entities._connection import _Connection as Connection
from promptflow.contracts._run_management import RunDetail, RunMetadata

from ..utils import PFSOperations


def create_run_against_multi_line_data(client: PFClient) -> Run:
    flow = "./tests/test_configs/flows/web_classification"
    data = "./tests/test_configs/datas/webClassification3.jsonl"
    return client.run(flow=flow, data=data, column_mapping={"url": "${data.url}"})


@pytest.mark.usefixtures("use_secrets_config_file")
@pytest.mark.e2etest
class TestRunAPIs:
    def test_list_runs(self, pf_client: PFClient, local_aoai_connection: Connection, pfs_op: PFSOperations) -> None:
        create_run_against_multi_line_data(pf_client)
        runs = pfs_op.list_runs().json
        assert len(runs) >= 1

    def test_get_run(self, pf_client: PFClient, local_aoai_connection: Connection, pfs_op: PFSOperations) -> None:
        run = create_run_against_multi_line_data(pf_client)
        run_from_pfs = pfs_op.get_run(name=run.name).json
        assert run_from_pfs["name"] == run.name
        assert run_from_pfs["properties"] == run.properties

    def test_get_not_exist_run(self, pfs_op: PFSOperations) -> None:
        random_name = str(uuid.uuid4())
        response = pfs_op.get_run(name=random_name)
        assert response.status_code == 404

    def test_get_run_metadata(
        self, pf_client: PFClient, local_aoai_connection: Connection, pfs_op: PFSOperations
    ) -> None:
        run = create_run_against_multi_line_data(pf_client)
        metadata = pfs_op.get_run_metadata(name=run.name).json
        for field in fields(RunMetadata):
            assert field.name in metadata
        assert metadata["name"] == run.name
        assert metadata["display_name"] == run.display_name

    def test_get_run_detail(
        self, pf_client: PFClient, local_aoai_connection: Connection, pfs_op: PFSOperations
    ) -> None:
        run = create_run_against_multi_line_data(pf_client)
        detail = pfs_op.get_run_detail(name=run.name).json
        for field in fields(RunDetail):
            assert field.name in detail
        assert isinstance(detail["flow_runs"], list)
        assert len(detail["flow_runs"]) == 3
        assert isinstance(detail["node_runs"], list)
