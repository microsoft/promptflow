import pytest

from promptflow._sdk._errors import RunOperationParameterError
from promptflow.azure import PFClient


@pytest.mark.unittest
class TestPFClientAzure:
    def test_input_output_portal_url_parser(self, remote_client):
        runs_op = remote_client.runs

        # test input with datastore path
        input_datastore_path = (
            "azureml://datastores/workspaceblobstore/paths/LocalUpload/312cca2af474e5f895013392b6b38f45/data.jsonl"
        )
        expected_input_portal_url = (
            f"https://ml.azure.com/data/datastore/workspaceblobstore/edit?wsid={runs_op._common_azure_url_pattern}"
            f"&activeFilePath=LocalUpload/312cca2af474e5f895013392b6b38f45/data.jsonl#browseTab"
        )
        assert runs_op._get_input_portal_url_from_input_uri(input_datastore_path) == expected_input_portal_url

        # test input with asset id
        input_asset_id = (
            "azureml://locations/eastus/workspaces/f40fcfba-ed15-4c0c-a522-6798d8d89094/data/hod-qa-sample/versions/1"
        )
        expected_input_portal_url = (
            f"https://ml.azure.com/data/hod-qa-sample/1/details?wsid={runs_op._common_azure_url_pattern}"
        )
        assert runs_op._get_input_portal_url_from_input_uri(input_asset_id) == expected_input_portal_url

        # test output with asset id
        output_asset_id = (
            "azureml://locations/eastus/workspaces/f40fcfba-ed15-4c0c-a522-6798d8d89094/data"
            "/azureml_d360affb-c01f-460f-beca-db9a8b88b625_output_data_flow_outputs/versions/1"
        )
        expected_output_portal_url = (
            "https://ml.azure.com/data/azureml_d360affb-c01f-460f-beca-db9a8b88b625_output_data_flow_outputs/1/details"
            f"?wsid={runs_op._common_azure_url_pattern}"
        )
        assert runs_op._get_portal_url_from_asset_id(output_asset_id) == expected_output_portal_url

    def test_wrong_client_parameters(self):
        # test wrong client parameters
        with pytest.raises(RunOperationParameterError, match="You have passed in the wrong parameter name"):
            PFClient(
                subscription_id="fake_subscription_id",
                resource_group="fake_resource_group",
                workspace_name="fake_workspace_name",
            )
