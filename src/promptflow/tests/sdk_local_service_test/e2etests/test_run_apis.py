# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from dataclasses import fields

import pytest

from ..utils import LocalServiceOperations
from promptflow import PFClient
from promptflow._sdk.entities import Run
from promptflow._sdk.entities._connection import _Connection as Connection
from promptflow.contracts._run_management import RunDetail, RunMetadata


def create_run_against_multi_line_data(client: PFClient) -> Run:
    flow = "./tests/test_configs/flows/web_classification"
    data = "./tests/test_configs/datas/webClassification3.jsonl"
    return client.run(flow=flow, data=data, column_mapping={"url": "${data.url}"})


@pytest.mark.usefixtures("use_secrets_config_file")
@pytest.mark.e2etest
class TestRunAPIs:
    def test_heartbeat(self, local_service_op: LocalServiceOperations) -> None:
        response = local_service_op.heartbeat()
        assert response.status_code == 204

    def test_list_runs(
        self, pf_client: PFClient, local_aoai_connection: Connection, local_service_op: LocalServiceOperations
    ) -> None:
        create_run_against_multi_line_data(pf_client)
        response = local_service_op.list()
        assert len(response) >= 1

    def test_get_run(
        self, pf_client: PFClient, local_aoai_connection: Connection, local_service_op: LocalServiceOperations
    ) -> None:
        run = create_run_against_multi_line_data(pf_client)
        response = local_service_op.get(name=run.name)
        assert response["name"] == run.name
        assert response["properties"] == run.properties

    def test_get_run_metadata(
        self, pf_client: PFClient, local_aoai_connection: Connection, local_service_op: LocalServiceOperations
    ) -> None:
        run = create_run_against_multi_line_data(pf_client)
        metadata = local_service_op.get_metadata(name=run.name)
        for field in fields(RunMetadata):
            assert field.name in metadata
        assert metadata["name"] == run.name
        assert metadata["display_name"] == run.display_name

    def test_get_run_detail(
        self, pf_client: PFClient, local_aoai_connection: Connection, local_service_op: LocalServiceOperations
    ) -> None:
        run = create_run_against_multi_line_data(pf_client)
        detail = local_service_op.get_metadata(name=run.name)
        for field in fields(RunDetail):
            assert field.name in detail
        assert isinstance(detail["flow_runs"], list)
        assert len(detail["flow_runs"]) == 3
        assert isinstance(detail["node_runs"], list)
