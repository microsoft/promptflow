# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import copy
import uuid
from pathlib import Path
from unittest import mock

import pandas as pd
import pytest

from promptflow.azure import BulkFlowRun
from promptflow.azure._utils._url_utils import BulkRunId, BulkRunURL
from promptflow.azure.constants import FlowType
from promptflow.sdk._load_functions import load_run
from promptflow.utils.utils import is_in_ci_pipeline

PROMOTFLOW_ROOT = Path(__file__) / "../../../.."
FLOWS_DIR = Path("./tests/test_configs/flows")


def _configure_for_bulk_flow_run():
    # BulkFlowRun has operation init in __init__
    # so we need to configure it, even in this unit test
    from azure.ai.ml import MLClient
    from azure.identity import AzureCliCredential, DefaultAzureCredential

    from promptflow.azure import configure

    cred = DefaultAzureCredential()
    if is_in_ci_pipeline():
        cred = AzureCliCredential()

    client = MLClient(
        credential=cred,
        subscription_id="96aede12-2f73-41cb-b983-6d11a904839b",
        resource_group_name="promptflow",
        workspace_name="promptflow-canary-dev",
    )
    configure(client=client)


@pytest.mark.unittest
class TestBulkFlowRun:
    def test_bulk_flow_run_details(self):
        # create a mock bulk flow run
        _configure_for_bulk_flow_run()

        # patch init for FlowJobOperations
        def _mock_init(*args, **kwargs):
            pass

        with mock.patch(
            "promptflow.azure.operations._flow_job_operations.FlowJobOperations.__init__", side_effect=_mock_init
        ):
            run = BulkFlowRun(flow_id="flow_id", bulk_test_id="bulk_test_id", runtime="runtime")

        run._flow_type = FlowType.STANDARD

        # template and assert helper function
        child_run_info_template = [
            {
                "index": 0,
                "inputs": {
                    "input1": 0,
                    "input2": "0",
                },
                "output": {"output1": "x"},
                "variant_id": "variant_0",
            }
        ]

        def _assert_details(_df: pd.DataFrame, index: int = None, variant_id: str = None):
            assert _df.iloc[0]["index"] == 0 if index is None else index
            assert _df.iloc[0]["input1"] == 0
            assert _df.iloc[0]["input2"] == "0"
            assert _df.iloc[0]["output1"] == "x"
            assert _df.iloc[0]["variant_id"] == "variant_0" if variant_id is None else variant_id

        # case1: normal
        child_run_infos = copy.deepcopy(child_run_info_template)
        details = run._from_child_run_infos(child_run_infos)
        _assert_details(details)

        # case2: variant_id in inputs - bulk test toward evaluation flow run
        child_run_infos = copy.deepcopy(child_run_info_template)
        child_run_infos[0]["inputs"].update({"variant_id": "variant_1"})
        details = run._from_child_run_infos(child_run_infos)
        _assert_details(details, variant_id="variant_1")

        # case3: both index and variant_id in inputs - not sure if there is real scenario
        child_run_infos = copy.deepcopy(child_run_info_template)
        child_run_infos[0]["inputs"].update({"index": 1, "variant_id": "variant_1"})
        details = run._from_child_run_infos(child_run_infos)
        _assert_details(details, index=1, variant_id="variant_1")

    def test_url_parse(self):
        flow_id = (
            "azureml://experiment/3e123da1-f9a5-4c91-9234-8d9ffbb39ff5/flow/"
            "0ab9d2dd-3bac-4b68-bb28-12af959b1165/bulktest/715efeaf-b0b4-4778-b94a-2538152b8766/"
            "run/f88faee6-e510-45b7-9e63-08671b30b3a2"
        )
        flow_id = BulkRunId(flow_id)
        assert flow_id.experiment_id == "3e123da1-f9a5-4c91-9234-8d9ffbb39ff5"
        assert flow_id.flow_id == "0ab9d2dd-3bac-4b68-bb28-12af959b1165"
        assert flow_id.bulk_test_id == "715efeaf-b0b4-4778-b94a-2538152b8766"

        flow_run_url = (
            "https://ml.azure.com/prompts/flow/3e123da1-f9a5-4c91-9234-8d9ffbb39ff5/"
            "0ab9d2dd-3bac-4b68-bb28-12af959b1165/bulktest/715efeaf-b0b4-4778-b94a-2538152b8766/"
            "details?wsid=/subscriptions/96aede12-2f73-41cb-b983-6d11a904839b/resourcegroups/promptflow/"
            "providers/Microsoft.MachineLearningServices/workspaces/promptflow-eastus"
        )
        flow_url = BulkRunURL(flow_run_url)
        assert flow_url.experiment_id == "3e123da1-f9a5-4c91-9234-8d9ffbb39ff5"
        assert flow_url.flow_id == "0ab9d2dd-3bac-4b68-bb28-12af959b1165"
        assert flow_url.bulk_test_id == "715efeaf-b0b4-4778-b94a-2538152b8766"

    def test_load_yaml_run_with_resources(self):
        source = f"{FLOWS_DIR}/runs/sample_bulk_run_with_resources.yaml"
        run = load_run(source=source, params_override=[{"name": str(uuid.uuid4())}])
        assert run._resources["instance_type"] == "Standard_DSV2"
        assert run._resources["idle_time_before_shutdown_minutes"] == 60
