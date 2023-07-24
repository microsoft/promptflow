# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import pydash
import pytest

from promptflow.azure import configure
from promptflow.azure._configuration import _get_connection_operations
from promptflow.azure._restclient.flow_service_caller import FlowRequestException
from promptflow.connections import AzureOpenAIConnection, CustomConnection
from promptflow.contracts.types import Secret
from promptflow.sdk.entities._connection import _Connection


@pytest.fixture
def connection_ops(ml_client):
    configure(client=ml_client)
    result = _get_connection_operations()
    yield result


@pytest.mark.e2etest
class TestConnectionOperations:
    @pytest.mark.skip(reason="Skip to avoid flooded connections in workspace.")
    def test_connection_get_create_delete(self, connection_ops):

        connection = _Connection(
            name="test_connection_1",
            type="AzureOpenAI",
            configs=AzureOpenAIConnection(
                api_key=Secret("test_key"),
                api_base="test_base",
                api_type="azure",
                api_version="2023-03-15-preview",
            ),
        )
        try:
            result = connection_ops.get(name=connection.name)
        except FlowRequestException:
            result = connection_ops.create_or_update(connection)
        config_dict = pydash.omit(result._to_dict(), "configs.api_key")
        assert config_dict == {
            "name": "test_connection_1",
            "connection_type": "AzureOpenAI",
            "connection_scope": "User",
            "configs": {"api_base": "test_base", "api_type": "azure", "api_version": "2023-03-15-preview"},
        }

        # soft delete
        connection_ops.delete(name=connection.name)

    @pytest.mark.skip(reason="Skip to avoid flooded connections in workspace.")
    def test_custom_connection_create(self, connection_ops):

        connection = _Connection(
            name="test_connection_2", type="Custom", custom_configs=CustomConnection(a="1", b=Secret("2"))
        )

        try:
            result = connection_ops.get(name=connection.name)
        except FlowRequestException:
            result = connection_ops.create_or_update(connection)
        config_dict = pydash.omit(result._to_dict(), "custom_configs")
        assert config_dict == {"connection_scope": "User", "connection_type": "Custom", "name": "test_connection_2"}

        # soft delete
        connection_ops.delete(name=connection.name)

    def test_list_connection_spec(self, connection_ops):
        result = {v.connection_type: v._to_dict() for v in connection_ops.list_connection_specs()}
        # Assert custom keys type
        assert "Custom" in result
        assert result["Custom"] == {
            "module": "promptflow.connections",
            "connection_type": "Custom",
            "flow_value_type": "CustomConnection",
            "config_specs": [],
        }
        # assert strong type
        assert "AzureOpenAI" in result
        assert result["AzureOpenAI"] == {
            "module": "promptflow.connections",
            "connection_type": "AzureOpenAI",
            "flow_value_type": "AzureOpenAIConnection",
            "config_specs": [
                {"name": "api_key", "display_name": "API key", "config_value_type": "Secret", "is_optional": False},
                {"name": "api_base", "display_name": "API base", "config_value_type": "String", "is_optional": False},
                {
                    "name": "api_type",
                    "display_name": "API type",
                    "config_value_type": "String",
                    "default_value": "azure",
                    "is_optional": False,
                },
                {
                    "name": "api_version",
                    "display_name": "API version",
                    "config_value_type": "String",
                    "default_value": "2023-03-15-preview",
                    "is_optional": False,
                },
            ],
        }
