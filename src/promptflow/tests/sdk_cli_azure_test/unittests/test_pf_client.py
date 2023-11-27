# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import mock
import pytest

from promptflow import PFClient
from promptflow._sdk.operations._connection_operations import ConnectionOperations
from promptflow._sdk.operations._local_azure_connection_operations import LocalAzureConnectionOperations

from ..recording_utilities import is_live

AZUREML_RESOURCE_PROVIDER = "Microsoft.MachineLearningServices"
RESOURCE_ID_FORMAT = "/subscriptions/{}/resourceGroups/{}/providers/{}/workspaces/{}"


@pytest.mark.sdk_test
@pytest.mark.e2etest
class TestPFClient:
    # Test pf client when connection provider is azureml.
    # This tests suites need azure dependencies.
    @pytest.mark.skipif(condition=not is_live(), reason="This test requires an actual PFClient")
    def test_connection_provider(self, subscription_id: str, resource_group_name: str, workspace_name: str):
        target = "promptflow._sdk._pf_client.Configuration"
        with mock.patch(target) as mocked:
            mocked.return_value.get_connection_provider.return_value = "abc"
            with pytest.raises(ValueError) as e:
                client = PFClient()
                assert client.connections
            assert "Unsupported connection provider" in str(e.value)

        with mock.patch(target) as mocked:
            mocked.return_value.get_connection_provider.return_value = "azureml:xx"
            with pytest.raises(ValueError) as e:
                client = PFClient()
                assert client.connections
            assert "Malformed connection provider string" in str(e.value)

        with mock.patch(target) as mocked:
            mocked.return_value.get_connection_provider.return_value = "local"
            client = PFClient()
            assert isinstance(client.connections, ConnectionOperations)

        with mock.patch(target) as mocked:
            mocked.return_value.get_connection_provider.return_value = "azureml:" + RESOURCE_ID_FORMAT.format(
                subscription_id, resource_group_name, AZUREML_RESOURCE_PROVIDER, workspace_name
            )
            client = PFClient()
            assert isinstance(client.connections, LocalAzureConnectionOperations)

        client = PFClient(
            config={
                "connection.provider": "azureml:"
                + RESOURCE_ID_FORMAT.format(
                    subscription_id, resource_group_name, AZUREML_RESOURCE_PROVIDER, workspace_name
                )
            }
        )
        assert isinstance(client.connections, LocalAzureConnectionOperations)

    def test_local_azure_connection_extract_workspace(self):
        res = LocalAzureConnectionOperations._extract_workspace(
            "azureml:/subscriptions/123/resourceGroups/456/providers/Microsoft.MachineLearningServices/workspaces/789"
        )
        assert res == ("123", "456", "789")

        res = LocalAzureConnectionOperations._extract_workspace(
            "azureml:/subscriptions/123/resourcegroups/456/workspaces/789"
        )
        assert res == ("123", "456", "789")

        with pytest.raises(ValueError) as e:
            LocalAzureConnectionOperations._extract_workspace("azureml:xx")
        assert "Malformed connection provider string" in str(e.value)

        with pytest.raises(ValueError) as e:
            LocalAzureConnectionOperations._extract_workspace(
                "azureml:/subscriptions/123/resourceGroups/456/providers/Microsoft.MachineLearningServices/workspaces/"
            )
        assert "Malformed connection provider string" in str(e.value)
