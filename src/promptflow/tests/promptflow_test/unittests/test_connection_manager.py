import pytest

from promptflow.connections import AzureOpenAIConnection, BingConnection
from promptflow.contracts.tool import ConnectionType
from promptflow.core.connection_manager import ConnectionManager


def get_new_connection_dict():
    return {
        "azure_open_ai_connection": {
            "type": "AzureOpenAIConnection",
            "value": {
                "api_key": "<azure-openai-key>",
                "api_base": "https://gpt-test-eus.openai.azure.com/",
                "api_type": "azure",
                "api_version": "2023-03-15-preview",
            },
        },
        "bing_connection": {
            "type": "BingConnection",
            "value": {
                "api_key": "<bing-key>",
                "url": "https://api.bing.microsoft.com/v7.0/search",
            },
            "module": "promptflow.connections",
        },
        "custom_connection": {
            "type": "CustomConnection",
            "value": {
                "api_key": "<your-key>",
                "url": "https://api.bing.microsoft.com/v7.0/search",
            },
            "module": "promptflow.connections",
            "secret_keys": ["api_key"],
        },
    }


def get_legacy_connection_dict():
    return {
        "azure_open_ai_connection": {
            "api_key": "<azure-openai-key>",
            "api_base": "https://gpt-test-eus.openai.azure.com/",
            "api_type": "azure",
            "api_version": "2023-03-15-preview",
        },
        "bing_connection": {
            "api_key": "<bing-key>",
            "url": "https://api.bing.microsoft.com/v7.0/search",
        },
    }


@pytest.mark.unittest
class TestConnectionManager:
    def test_legacy_format_test(self) -> None:
        assert ConnectionManager.is_legacy_connections(get_new_connection_dict()) is False
        assert ConnectionManager.is_legacy_connections(get_legacy_connection_dict()) is True

    def test_build_connections(self):
        new_connection = get_new_connection_dict()
        # Add not exist key
        new_connection["azure_open_ai_connection"]["value"]["not_exist"] = "test"
        connection_manager = ConnectionManager(new_connection)
        assert len(connection_manager._connections) == 3
        assert isinstance(connection_manager.get("azure_open_ai_connection"), AzureOpenAIConnection)
        assert isinstance(connection_manager.get("bing_connection"), BingConnection)
        assert connection_manager.to_connections_dict() == new_connection

    def test_serialize(self):
        new_connection = get_new_connection_dict()
        connection_manager = ConnectionManager(new_connection)
        assert (
            ConnectionType.serialize_conn(connection_manager.get("azure_open_ai_connection"))
            == "azure_open_ai_connection"
        )
        assert ConnectionType.serialize_conn(connection_manager.get("bing_connection")) == "bing_connection"
        assert ConnectionType.serialize_conn(connection_manager.get("custom_connection")) == "custom_connection"

    def test_get_secret_list(self):
        new_connection = get_new_connection_dict()
        connection_manager = ConnectionManager(new_connection)
        expected_list = ["<azure-openai-key>", "<bing-key>", "<your-key>"]
        assert set(connection_manager.get_secret_list()) == set(expected_list)

    def test_is_secret(self):
        new_connection = get_new_connection_dict()
        connection_manager = ConnectionManager(new_connection)
        connection = connection_manager.get("custom_connection")
        assert connection.is_secret("api_key") is True
        assert connection.is_secret("url") is False
