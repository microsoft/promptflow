# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import pytest

from promptflow.azure._utils._url_utils import BulkRunId, BulkRunURL


@pytest.mark.unittest
class TestUtils:
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
