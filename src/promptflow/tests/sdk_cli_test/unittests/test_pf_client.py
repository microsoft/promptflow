# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import mock
import pytest
from azure.ai.ml.constants._common import AZUREML_RESOURCE_PROVIDER, RESOURCE_ID_FORMAT

from promptflow import PFClient
from promptflow._core.operation_context import OperationContext
from promptflow._sdk.operations._connection_operations import ConnectionOperations
from promptflow._sdk.operations._local_azure_connection_operations import LocalAzureConnectionOperations


@pytest.mark.sdk_test
@pytest.mark.e2etest
class TestPFClient:
    def test_pf_client_user_agent(self):
        PFClient()
        assert "promptflow-sdk" in OperationContext.get_instance().get_user_agent()

    def test_connection_provider(self):
        target = "promptflow._sdk._pf_client.Configuration"
        with mock.patch(target) as mocked:
            mocked.get_instance.return_value.get_connection_provider.return_value = "abc"
            with pytest.raises(ValueError) as e:
                client = PFClient()
                assert client.connections
            assert "Unsupported connection provider" in str(e.value)

        with mock.patch(target) as mocked:
            mocked.get_instance.return_value.get_connection_provider.return_value = "azureml:xx"
            with pytest.raises(ValueError) as e:
                client = PFClient()
                assert client.connections
            assert "Malformed connection provider string" in str(e.value)

        with mock.patch(target) as mocked:
            mocked.get_instance.return_value.get_connection_provider.return_value = "local"
            client = PFClient()
            assert isinstance(client.connections, ConnectionOperations)

        with mock.patch(target) as mocked:
            mocked.get_instance.return_value.get_connection_provider.return_value = (
                "azureml:"
                + RESOURCE_ID_FORMAT.format(
                    "96aede12-2f73-41cb-b983-6d11a904839b", "promptflow", AZUREML_RESOURCE_PROVIDER, "promptflow-eastus"
                )
            )
            client = PFClient()
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
