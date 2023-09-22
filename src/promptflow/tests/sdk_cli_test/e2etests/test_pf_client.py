# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from typing import Callable

import mock
import pytest
from azure.ai.ml.constants._common import AZUREML_RESOURCE_PROVIDER, RESOURCE_ID_FORMAT

from promptflow import PFClient
from promptflow._core.operation_context import OperationContext
from promptflow._sdk.operations._connection_operations import ConnectionOperations
from promptflow._sdk.operations._local_azure_connection_operations import LocalAzureConnectionOperations


class MockConfiguration(object):
    _instance = None

    def __init__(self, connection_provider: Callable):
        setattr(self, "get_connection_provider", connection_provider)

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = MockConfiguration()
        return cls._instance


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
