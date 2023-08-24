# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from pathlib import Path

import pytest

from promptflow._cli._pf_azure._flow import create_flow, list_flows
from promptflow.azure._load_functions import load_flow

tests_root_dir = Path(__file__).parent.parent.parent
flow_test_dir = tests_root_dir / "test_configs/flows"
data_dir = tests_root_dir / "test_configs/datas"


@pytest.fixture
def client(remote_client):
    return remote_client


# TODO: enable the following tests after test CI can access test workspace
@pytest.mark.e2etest
@pytest.mark.skip(reason="This test is not ready yet.")
class TestFlow:
    def test_flow_no_variants_remote_file(self, client, runtime):
        local_file = flow_test_dir / "meta_files/remote_flow_short_path.meta.yaml"

        flow = load_flow(source=local_file)

        run = flow.submit_bulk_run(
            data=data_dir / "classificationAccuracy.csv",
            connections={},
            runtime=runtime,
        )
        print(run)

    def test_flow_without_variants(self, client, runtime):
        local_file = flow_test_dir / "classification_accuracy_evaluation"

        flow = load_flow(source=local_file)

        run = flow.submit_bulk_run(
            data=data_dir / "classificationAccuracy.csv",
            connections={},
            runtime=runtime,
            use_flow_snapshot_to_submit=True,
        )
        print(run)

    def test_flow(self, client, runtime):
        local_file = flow_test_dir / "web_classification/"

        flow = load_flow(source=local_file)

        run = flow.submit_bulk_run(
            data=flow_test_dir / "webClassification20.csv",
            connections={},
            runtime=runtime,
            tuning_node_name="summarize_text_content",
            use_flow_snapshot_to_submit=False,
        )

        print(run)

    def test_crud_flow(self, client):
        flow_source = flow_test_dir / "web_classification/"
        result = create_flow(
            source=flow_source,
            subscription_id=client.subscription_id,
            resource_group=client.resource_group_name,
            workspace_name=client.workspace_name,
        )
        print(result.as_dict())

    def test_list_flows(self, client):
        flows = list_flows(
            subscription_id=client.subscription_id,
            resource_group=client.resource_group_name,
            workspace_name=client.workspace_name,
        )
        print(flows)
