import uuid
from pathlib import Path

import pydash
import pytest

from promptflow._sdk._constants import SCRUBBED_VALUE, CustomStrongTypeConnectionConfigs
from promptflow._sdk._pf_client import PFClient
from promptflow._sdk.entities import CustomStrongTypeConnection
from promptflow.contracts.types import Secret


class MyCustomConnection(CustomStrongTypeConnection):
    api_key: Secret
    api_base: str


_client = PFClient()

TEST_ROOT = Path(__file__).parent.parent.parent
CONNECTION_ROOT = TEST_ROOT / "test_configs/connections"


@pytest.mark.cli_test
@pytest.mark.e2etest
class TestCustomStrongTypeConnection:
    def test_connection_operations(self):
        name = f"Connection_{str(uuid.uuid4())[:4]}"
        conn = MyCustomConnection(name=name, secrets={"api_key": "test"}, configs={"api_base": "test"})
        # Create
        _client.connections.create_or_update(conn)
        # Get
        result = _client.connections.get(name)
        assert pydash.omit(result._to_dict(), ["created_date", "last_modified_date", "name"]) == {
            "module": "promptflow.connections",
            "type": "custom",
            "configs": {
                "api_base": "test",
                "promptflow.connection.custom_type": "MyCustomConnection",
                "promptflow.connection.module": "sdk_cli_test.e2etests.test_custom_strong_type_connection",
            },
            "secrets": {"api_key": "******"},
        }
        # Update
        conn.configs["api_base"] = "test2"
        result = _client.connections.create_or_update(conn)
        assert pydash.omit(result._to_dict(), ["created_date", "last_modified_date", "name"]) == {
            "module": "promptflow.connections",
            "type": "custom",
            "configs": {
                "api_base": "test2",
                "promptflow.connection.custom_type": "MyCustomConnection",
                "promptflow.connection.module": "sdk_cli_test.e2etests.test_custom_strong_type_connection",
            },
            "secrets": {"api_key": "******"},
        }
        # List
        result = _client.connections.list()
        assert len(result) > 0
        # Delete
        _client.connections.delete(name)
        with pytest.raises(Exception) as e:
            _client.connections.get(name)
        assert "is not found." in str(e.value)

    def test_connection_update(self):
        name = f"Connection_{str(uuid.uuid4())[:4]}"
        conn = MyCustomConnection(name=name, secrets={"api_key": "test"}, configs={"api_base": "test"})
        # Create
        _client.connections.create_or_update(conn)
        # Get
        custom_conn = _client.connections.get(name)
        assert pydash.omit(custom_conn._to_dict(), ["created_date", "last_modified_date", "name"]) == {
            "module": "promptflow.connections",
            "type": "custom",
            "configs": {
                "api_base": "test",
                "promptflow.connection.custom_type": "MyCustomConnection",
                "promptflow.connection.module": "sdk_cli_test.e2etests.test_custom_strong_type_connection",
            },
            "secrets": {"api_key": "******"},
        }
        # Update
        custom_conn.configs["api_base"] = "test2"
        result = _client.connections.create_or_update(custom_conn)
        assert pydash.omit(result._to_dict(), ["created_date", "last_modified_date", "name"]) == {
            "module": "promptflow.connections",
            "type": "custom",
            "configs": {
                "api_base": "test2",
                "promptflow.connection.custom_type": "MyCustomConnection",
                "promptflow.connection.module": "sdk_cli_test.e2etests.test_custom_strong_type_connection",
            },
            "secrets": {"api_key": "******"},
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
        conn = MyCustomConnection(name=name, secrets={"api_key": "test"}, configs={"api_base": "test"})
        result = _client.connections.create_or_update(conn)
        assert result.secrets["api_key"] == SCRUBBED_VALUE
        # Update api_base only Assert no exception
        result.configs["api_base"] = "test2"
        result = _client.connections.create_or_update(result)
        assert result._to_dict()["configs"]["api_base"] == "test2"
        # Assert value not scrubbed
        assert result._secrets["api_key"] == "test"
        _client.connections.delete(name)
        # Invalid update
        with pytest.raises(Exception) as e:
            result._secrets = {}
            _client.connections.create_or_update(result)
        assert "secrets ['api_key'] value invalid, please fill them" in str(e.value)

    def test_connection_get_and_update_with_key(self):
        # Test api key not updated
        name = f"Connection_{str(uuid.uuid4())[:4]}"
        conn = MyCustomConnection(name=name, secrets={"api_key": "test"}, configs={"api_base": "test"})
        assert conn.api_base == "test"
        assert conn.configs["api_base"] == "test"

        result = _client.connections.create_or_update(conn)
        converted_conn = result._convert_to_custom_strong_type(
            module=__class__.__module__, to_class="MyCustomConnection"
        )

        assert isinstance(converted_conn, MyCustomConnection)
        assert converted_conn.api_base == "test"
        converted_conn.api_base = "test2"
        assert converted_conn.api_base == "test2"
        assert converted_conn.configs["api_base"] == "test2"

    @pytest.mark.parametrize(
        "file_name, expected_updated_item, expected_secret_item",
        [
            ("custom_strong_type_connection.yaml", ("api_base", "new_value"), ("api_key", "<to-be-replaced>")),
        ],
    )
    def test_upsert_connection_from_file(
        self, install_custom_tool_pkg, file_name, expected_updated_item, expected_secret_item
    ):
        from promptflow._cli._pf._connection import _upsert_connection_from_file

        name = f"Connection_{str(uuid.uuid4())[:4]}"
        result = _upsert_connection_from_file(file=CONNECTION_ROOT / file_name, params_override=[{"name": name}])
        assert result is not None
        assert result.configs[CustomStrongTypeConnectionConfigs.PROMPTFLOW_MODULE_KEY] == "my_tool_package.connections"
        update_file_name = f"update_{file_name}"
        result = _upsert_connection_from_file(file=CONNECTION_ROOT / update_file_name, params_override=[{"name": name}])
        # Test secrets not updated, and configs updated
        assert (
            result.configs[expected_updated_item[0]] == expected_updated_item[1]
        ), "Assert configs updated failed, expected: {}, actual: {}".format(
            expected_updated_item[1], result.configs[expected_updated_item[0]]
        )
        assert (
            result._secrets[expected_secret_item[0]] == expected_secret_item[1]
        ), "Assert secrets not updated failed, expected: {}, actual: {}".format(
            expected_secret_item[1], result._secrets[expected_secret_item[0]]
        )
