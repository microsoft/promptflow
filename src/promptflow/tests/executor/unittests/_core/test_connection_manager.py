import builtins
import json
from unittest import mock

import pytest

from promptflow._constants import DEFAULT_ENCODING, PROMPTFLOW_CONNECTIONS
from promptflow._core.connection_manager import ConnectionManager
from promptflow.connections import AzureOpenAIConnection
from promptflow.contracts.tool import ConnectionType


def get_connection_dict():
    return {
        "azure_open_ai_connection": {
            "type": "AzureOpenAIConnection",
            "value": {
                "api_key": "<azure-openai-key>",
                "api_base": "<api-base>",
                "api_type": "azure",
                "api_version": "2023-07-01-preview",
            },
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


@pytest.mark.unittest
class TestConnectionManager:
    def test_build_connections(self):
        new_connection = get_connection_dict()
        # Add not exist key
        new_connection["azure_open_ai_connection"]["value"]["not_exist"] = "test"
        connection_manager = ConnectionManager(new_connection)
        assert len(connection_manager._connections) == 2
        assert isinstance(connection_manager.get("azure_open_ai_connection"), AzureOpenAIConnection)
        assert connection_manager.to_connections_dict() == new_connection

    def test_serialize(self):
        new_connection = get_connection_dict()
        connection_manager = ConnectionManager(new_connection)
        assert (
            ConnectionType.serialize_conn(connection_manager.get("azure_open_ai_connection"))
            == "azure_open_ai_connection"
        )
        assert ConnectionType.serialize_conn(connection_manager.get("custom_connection")) == "custom_connection"

    def test_get_secret_list(self):
        new_connection = get_connection_dict()
        connection_manager = ConnectionManager(new_connection)
        expected_list = ["<azure-openai-key>", "<your-key>"]
        assert set(connection_manager.get_secret_list()) == set(expected_list)

    def test_is_secret(self):
        new_connection = get_connection_dict()
        connection_manager = ConnectionManager(new_connection)
        connection = connection_manager.get("custom_connection")
        assert connection.is_secret("api_key") is True
        assert connection.is_secret("url") is False

    def test_load_connection_file_with_non_ascii_value(self, tmp_path, monkeypatch):
        """Loading a connection file with non-ASCII content must round-trip correctly."""
        new_connection = get_connection_dict()
        new_connection["custom_connection"]["value"]["url"] = "https://example.com/日本語"
        connection_file = tmp_path / "connections.json"
        connection_file.write_text(json.dumps(new_connection, ensure_ascii=False), encoding="utf-8")
        monkeypatch.setenv(PROMPTFLOW_CONNECTIONS, str(connection_file))

        connection_manager = ConnectionManager()
        assert connection_manager.get("custom_connection").url == "https://example.com/日本語"

    def test_load_connection_file_opens_with_explicit_utf8_and_closes_handle(self, tmp_path, monkeypatch):
        """The connection file must be opened with an explicit utf-8 encoding, via a
        context manager that closes the handle.

        This guards the regression at the open() call itself, rather than only by
        exercising decode behavior: on Linux the default locale encoding is usually
        already utf-8, so a content-only round-trip assertion would still pass on the
        pre-fix code and prove nothing there. Checking the arguments open() was called
        with catches the bug on every platform, because a bare open(path).read() with
        no context manager is wrong regardless of what the ambient locale happens to be.
        """
        new_connection = get_connection_dict()
        connection_file = tmp_path / "connections.json"
        connection_file.write_text(json.dumps(new_connection), encoding="utf-8")
        monkeypatch.setenv(PROMPTFLOW_CONNECTIONS, str(connection_file))

        real_open = builtins.open
        opened = []

        def tracking_open(file, *args, **kwargs):
            handle = real_open(file, *args, **kwargs)
            if str(file) == str(connection_file):
                opened.append((args, kwargs, handle))
            return handle

        with mock.patch("promptflow._core.connection_manager.open", side_effect=tracking_open):
            ConnectionManager()

        assert len(opened) == 1, f"expected exactly one open() call for the connection file, got {opened}"
        args, kwargs, handle = opened[0]
        assert kwargs.get("encoding") == DEFAULT_ENCODING, (
            f"connection file must be opened with encoding={DEFAULT_ENCODING!r}, "
            f"got args={args} kwargs={kwargs}"
        )
        assert handle.closed, "connection file handle must be closed (opened via a context manager)"
