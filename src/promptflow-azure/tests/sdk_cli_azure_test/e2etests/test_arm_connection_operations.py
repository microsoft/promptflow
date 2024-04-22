# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import pytest

from promptflow._sdk.entities import AzureOpenAIConnection, CustomConnection

from .._azure_utils import DEFAULT_TEST_TIMEOUT, PYTEST_TIMEOUT_METHOD


@pytest.fixture
def connection_ops(pf):
    return pf._arm_connections


@pytest.mark.timeout(timeout=DEFAULT_TEST_TIMEOUT, method=PYTEST_TIMEOUT_METHOD)
@pytest.mark.e2etest
@pytest.mark.usefixtures("vcr_recording")
class TestArmConnectionOperations:
    def test_get_connection(self, connection_ops):
        # Note: Secrets will be returned by arm api
        result = connection_ops.get(name="azure_open_ai_connection")
        assert isinstance(result, AzureOpenAIConnection)
        assert result.name == "azure_open_ai_connection"
        assert result.api_type == "azure"
        assert result.module == "promptflow.connections"
        assert "/subscriptions" in result.resource_id

        result = connection_ops.get(name="custom_connection")
        assert isinstance(result, CustomConnection)
        assert result.name == "custom_connection"
        assert result.configs == {}
        assert result.module == "promptflow.connections"
