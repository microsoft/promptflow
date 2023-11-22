# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from pathlib import Path
from unittest.mock import patch

import pytest

from promptflow.azure import PFClient

tests_root_dir = Path(__file__).parent.parent.parent
flow_test_dir = tests_root_dir / "test_configs/flows"
data_dir = tests_root_dir / "test_configs/datas"


@pytest.mark.unittest
class TestRunOperations:
    def test_input_output_portal_url_parser(self, pf: PFClient):
        runs_op = pf.runs
        common_azure_url_pattern = runs_op._service_caller._common_azure_url_pattern

        # test input with datastore path
        input_datastore_path = (
            "azureml://datastores/workspaceblobstore/paths/LocalUpload/312cca2af474e5f895013392b6b38f45/data.jsonl"
        )
        expected_input_portal_url = (
            f"https://ml.azure.com/data/datastore/workspaceblobstore/edit?wsid={common_azure_url_pattern}"
            f"&activeFilePath=LocalUpload/312cca2af474e5f895013392b6b38f45/data.jsonl#browseTab"
        )
        assert runs_op._get_input_portal_url_from_input_uri(input_datastore_path) == expected_input_portal_url

        # test input with asset id
        input_asset_id = (
            "azureml://locations/eastus/workspaces/f40fcfba-ed15-4c0c-a522-6798d8d89094/data/hod-qa-sample/versions/1"
        )
        expected_input_portal_url = f"https://ml.azure.com/data/hod-qa-sample/1/details?wsid={common_azure_url_pattern}"
        assert runs_op._get_input_portal_url_from_input_uri(input_asset_id) == expected_input_portal_url

        # test output with asset id
        output_asset_id = (
            "azureml://locations/eastus/workspaces/f40fcfba-ed15-4c0c-a522-6798d8d89094/data"
            "/azureml_d360affb-c01f-460f-beca-db9a8b88b625_output_data_flow_outputs/versions/1"
        )
        expected_output_portal_url = (
            "https://ml.azure.com/data/azureml_d360affb-c01f-460f-beca-db9a8b88b625_output_data_flow_outputs/1/details"
            f"?wsid={common_azure_url_pattern}"
        )
        assert runs_op._get_portal_url_from_asset_id(output_asset_id) == expected_output_portal_url

    def test_parse_run_portal_url(self, pf):

        run_id = "test_run_id"
        common_azure_url_pattern = pf._service_caller._common_azure_url_pattern

        # workspace is aml studio
        with patch.object(pf.runs._workspace, "_kind", "default"):
            url = pf.runs._get_run_portal_url(run_id)
            expected_portal_url = (
                f"https://ml.azure.com/prompts/flow/bulkrun/run/{run_id}/details?wsid={common_azure_url_pattern}"
            )
            assert url == expected_portal_url

        # workspace is azure ai studio
        with patch.object(pf.runs._workspace, "_kind", "project"):
            url = pf.runs._get_run_portal_url(run_id)
            expected_portal_url = (
                f"https://ai.azure.com/projectflows/bulkrun/run/{run_id}/details?wsid={common_azure_url_pattern}"
            )
            assert url == expected_portal_url
