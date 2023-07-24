import uuid

import pydash
import pytest

from promptflow.sdk._constants import SCRUBBED_VALUE
from promptflow.sdk._pf_client import PFClient
from promptflow.sdk.entities import AzureOpenAIConnection

_client = PFClient()


@pytest.mark.community_control_plane_cli_test
@pytest.mark.e2etest
class TestConnection:
    def test_connection_operations(self):
        name = f"Connection_{str(uuid.uuid4())[:4]}"
        conn = AzureOpenAIConnection(name=name, api_key="test", api_base="test")
        # Create
        _client.connections.create_or_update(conn)
        # Get
        result = _client.connections.get(name)
        assert pydash.omit(result._to_dict(), ["created_date", "last_modified_date", "name"]) == {
            "module": "promptflow.connections",
            "type": "AzureOpenAI",
            "api_key": "******",
            "api_base": "test",
            "api_type": "azure",
            "api_version": "2023-03-15-preview",
        }
        # Update
        conn.api_base = "test2"
        result = _client.connections.create_or_update(conn)
        assert pydash.omit(result._to_dict(), ["created_date", "last_modified_date", "name"]) == {
            "module": "promptflow.connections",
            "type": "AzureOpenAI",
            "api_key": "******",
            "api_base": "test2",
            "api_type": "azure",
            "api_version": "2023-03-15-preview",
        }
        # List
        result = _client.connections.list()
        assert len(result) > 0
        # Delete
        _client.connections.delete(name)
        with pytest.raises(Exception) as e:
            _client.connections.get(name)
        assert "is not found." in str(e.value)

    def test_connection_get_and_update(self):
        # Test api key not updated
        name = f"Connection_{str(uuid.uuid4())[:4]}"
        conn = AzureOpenAIConnection(name=name, api_key="test", api_base="test")
        result = _client.connections.create_or_update(conn)
        result.api_base = "test2"
        assert result.api_key == SCRUBBED_VALUE
        # Update
        with pytest.raises(Exception) as e:
            _client.connections.create_or_update(result)
        assert "secrets ['api_key'] must be filled again" in str(e.value)
        result.api_key = "test"
        # Assert no exception
        result = _client.connections.create_or_update(result)
        assert result._to_dict()["api_base"] == "test2"
        _client.connections.delete(name)
