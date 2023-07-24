# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from pathlib import Path

import pytest
from azure.ai.ml import MLClient
from azure.identity import DefaultAzureCredential

from promptflow._cli.pf_azure.pf_flow import create_flow, list_flows
from promptflow.azure import BulkFlowRun, BulkFlowRunInput, configure
from promptflow.azure._load_functions import load_flow

tests_root_dir = Path(__file__).parent.parent.parent
flow_test_dir = tests_root_dir / "test_configs/flows"


@pytest.fixture
def client():
    client = MLClient(
        credential=DefaultAzureCredential(),
        subscription_id="96aede12-2f73-41cb-b983-6d11a904839b",
        resource_group_name="promptflow",
        workspace_name="promptflow-eastus",
    )
    configure(client=client)
    return client


@pytest.fixture
def runtime():
    return "demo-mir"


# TODO: enable the following tests after test CI can access test workspace
@pytest.mark.e2etest
@pytest.mark.skip(reason="This test is not ready yet.")
class TestFlow:
    def test_flow_no_variants_remote_file(self, client, runtime):
        local_file = flow_test_dir / "meta_files/remote_flow_short_path.meta.yaml"

        flow = load_flow(source=local_file)

        run = flow.submit_bulk_run(
            data=flow_test_dir / "classificationAccuracy.csv",
            connections={},
            runtime=runtime,
        )
        print(run)

    def test_flow_without_variants(self, client, runtime):
        local_file = flow_test_dir / "classification_accuracy_evaluation"

        flow = load_flow(source=local_file)

        run = flow.submit_bulk_run(
            data=flow_test_dir / "classificationAccuracy.csv",
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

    def test_flow_with_eval(self, client, runtime):
        local_file = flow_test_dir / "web_classification/"

        flow = load_flow(source=local_file)

        baseline = flow.submit_bulk_run(
            data=flow_test_dir / "webClassification20.csv",
            tuning_node_name="summarize_text_content",
            runtime=runtime,
            use_flow_snapshot_to_submit=False,
        )

        baseline.wait_for_completion()

        classification_accuracy_eval = load_flow("azureml://flows/QnARelevanceEvaluation")

        bulk_flow_run_input = BulkFlowRunInput(
            data=flow_test_dir / "webClassification20.csv",
            variants=[baseline],
            inputs_mapping={"question": "data.url", "answer": "data.answer", "context": "data.evidence"},
        )

        baseline_accuracy = classification_accuracy_eval.submit_bulk_run(
            data=bulk_flow_run_input,
            runtime=runtime,
            use_flow_snapshot_to_submit=False,
        )

        print(baseline_accuracy)

    def test_flow_with_local_eval(self, client, runtime):
        bulk_run = flow_test_dir / "web_classification_no_variants/"
        flow = load_flow(source=bulk_run)

        baseline = flow.submit_bulk_run(
            data=flow_test_dir / "webClassification20.csv",
            tuning_node_name="summarize_text_content",
            runtime=runtime,
            use_flow_snapshot_to_submit=False,
        )

        baseline.wait_for_completion()

        eval_path = flow_test_dir / "classification_accuracy_evaluation/"
        classification_accuracy_eval = load_flow(source=eval_path)

        bulk_flow_run_input = BulkFlowRunInput(
            data=flow_test_dir / "webClassification20.csv",
            variants=[baseline],
            inputs_mapping={
                "groundtruth": "data.url",
                "prediction": "data.answer",
            },
        )

        baseline_accuracy = classification_accuracy_eval.submit_bulk_run(
            data=bulk_flow_run_input,
            runtime=runtime,
        )

        print(baseline_accuracy)

    def test_eval_with_remote_flow_run(self, client, runtime):
        bulk_test_url = (
            "https://ml.azure.com/prompts/flow/3e123da1-f9a5-4c91-9234-8d9ffbb39ff5/"
            "0ab9d2dd-3bac-4b68-bb28-12af959b1165/bulktest/715efeaf-b0b4-4778-b94a-2538152b8766/"
            "details?wsid=/subscriptions/96aede12-2f73-41cb-b983-6d11a904839b/resourcegroups/promptflow/"
            "providers/Microsoft.MachineLearningServices/workspaces/promptflow-eastus"
        )
        bulk_test_run = BulkFlowRun.from_url(bulk_test_url)

        eval_path = flow_test_dir / "classification_accuracy_evaluation/"
        classification_accuracy_eval = load_flow(source=eval_path)

        bulk_flow_run_input = BulkFlowRunInput(
            data=flow_test_dir / "webClassification20.csv",
            variants=[bulk_test_run],
            inputs_mapping={
                "groundtruth": "data.url",
                "prediction": "data.answer",
            },
        )

        baseline_accuracy = classification_accuracy_eval.submit_bulk_run(
            data=bulk_flow_run_input,
            runtime=runtime,
        )

        print(baseline_accuracy)

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
