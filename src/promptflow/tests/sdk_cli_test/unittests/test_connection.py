# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from promptflow._cli._pf._connection import validate_and_interactive_get_secrets
from promptflow._sdk._constants import SCRUBBED_VALUE
from promptflow._sdk._load_functions import _load_env_to_connection
from promptflow._sdk.entities._connection import (
    AzureContentSafetyConnection,
    AzureOpenAIConnection,
    CognitiveSearchConnection,
    CustomConnection,
    FormRecognizerConnection,
    OpenAIConnection,
    QdrantConnection,
    SerpConnection,
    WeaviateConnection,
    _Connection,
)

TEST_ROOT = Path(__file__).parent.parent.parent
CONNECTION_ROOT = TEST_ROOT / "test_configs/connections"


@pytest.mark.unittest
class TestConnection:
    @pytest.mark.parametrize(
        "file_name, class_name, init_param, expected",
        [
            (
                "azure_openai_connection.yaml",
                AzureOpenAIConnection,
                {
                    "name": "my_azure_open_ai_connection",
                    "api_type": "azure",
                    "api_version": "2023-07-01-preview",
                    "api_key": "<to-be-replaced>",
                    "api_base": "aoai-api-endpoint",
                },
                {
                    "module": "promptflow.connections",
                    "type": "azure_open_ai",
                },
            ),
            (
                "openai_connection.yaml",
                OpenAIConnection,
                {
                    "name": "my_open_ai_connection",
                    "api_key": "<to-be-replaced>",
                    "organization": "org",
                },
                {
                    "module": "promptflow.connections",
                    "type": "open_ai",
                },
            ),
            (
                "custom_connection.yaml",
                CustomConnection,
                {
                    "name": "my_custom_connection",
                    "configs": {"key1": "test1"},
                    "secrets": {"key2": "test2"},
                },
                {
                    "module": "promptflow.connections",
                    "type": "custom",
                },
            ),
            (
                "azure_content_safety_connection.yaml",
                AzureContentSafetyConnection,
                {
                    "name": "my_azure_content_safety_connection",
                    "api_key": "<to-be-replaced>",
                    "endpoint": "endpoint",
                    "api_version": "2023-04-30-preview",
                    "api_type": "Content Safety",
                },
                {
                    "module": "promptflow.connections",
                    "type": "azure_content_safety",
                },
            ),
            (
                "cognitive_search_connection.yaml",
                CognitiveSearchConnection,
                {
                    "name": "my_cognitive_search_connection",
                    "api_key": "<to-be-replaced>",
                    "api_base": "endpoint",
                    "api_version": "2023-07-01-Preview",
                },
                {
                    "module": "promptflow.connections",
                    "type": "cognitive_search",
                },
            ),
            (
                "serp_connection.yaml",
                SerpConnection,
                {
                    "name": "my_serp_connection",
                    "api_key": "<to-be-replaced>",
                },
                {
                    "module": "promptflow.connections",
                    "type": "serp",
                },
            ),
            (
                "form_recognizer_connection.yaml",
                FormRecognizerConnection,
                {
                    "name": "my_form_recognizer_connection",
                    "api_key": "<to-be-replaced>",
                    "endpoint": "endpoint",
                    "api_version": "2023-07-31",
                    "api_type": "Form Recognizer",
                },
                {
                    "module": "promptflow.connections",
                    "type": "form_recognizer",
                },
            ),
            (
                "qdrant_connection.yaml",
                QdrantConnection,
                {
                    "name": "my_qdrant_connection",
                    "api_key": "<to-be-replaced>",
                    "api_base": "endpoint",
                },
                {
                    "module": "promptflow_vectordb.connections",
                    "type": "qdrant",
                },
            ),
            (
                "weaviate_connection.yaml",
                WeaviateConnection,
                {
                    "name": "my_weaviate_connection",
                    "api_key": "<to-be-replaced>",
                    "api_base": "endpoint",
                },
                {
                    "module": "promptflow_vectordb.connections",
                    "type": "weaviate",
                },
            ),
        ],
    )
    def test_connection_load_dump(self, file_name, class_name, init_param, expected):
        conn = _Connection._load(data=yaml.safe_load(open(CONNECTION_ROOT / file_name)))
        expected = {**expected, **init_param}
        assert dict(conn._to_dict()) == expected
        assert class_name(**init_param)._to_dict() == expected

    def test_connection_load_from_env(self):
        connection = _load_env_to_connection(
            source=CONNECTION_ROOT / ".env", params_override=[{"name": "env_conn"}]
        )
        assert connection._to_dict() == {
            "name": "env_conn",
            "module": "promptflow.connections",
            "type": "custom",
            "configs": {},
            "secrets": {"aaa": "bbb", "ccc": "ddd"},
        }
        assert (
            connection.__str__()
            == """name: env_conn
module: promptflow.connections
type: custom
configs: {}
secrets:
  aaa: bbb
  ccc: ddd
"""
        )

    def test_connection_load_from_env_file_bad_case(self):
        # Test file not found
        with pytest.raises(FileNotFoundError) as e:
            _load_env_to_connection(
                source=CONNECTION_ROOT / "mock.env",
                params_override=[{"name": "env_conn"}],
            )
        assert "not found" in str(e.value)
        # Test file empty
        with pytest.raises(Exception) as e:
            _load_env_to_connection(
                source=CONNECTION_ROOT / "empty.env",
                params_override=[{"name": "env_conn"}],
            )
        assert "Load nothing" in str(e.value)

    def test_to_execution_connection_dict(self):
        # Assert custom connection build
        connection = CustomConnection(
            name="test_connection", configs={"a": "1"}, secrets={"b": "2"}
        )
        assert connection.to_execution_connection_dict() == {
            "module": "promptflow.connections",
            "secret_keys": ["b"],
            "type": "CustomConnection",
            "value": {"a": "1", "b": "2"},
        }

        # Assert strong type - AzureOpenAI
        connection = AzureOpenAIConnection(
            name="test_connection_1",
            type="AzureOpenAI",
            api_key="test_key",
            api_base="test_base",
            api_type="azure",
            api_version="2023-07-01-preview",
        )
        assert connection.to_execution_connection_dict() == {
            "module": "promptflow.connections",
            "secret_keys": ["api_key"],
            "type": "AzureOpenAIConnection",
            "value": {
                "api_base": "test_base",
                "api_key": "test_key",
                "api_type": "azure",
                "api_version": "2023-07-01-preview",
            },
        }

        # Assert strong type - OpenAI
        connection = OpenAIConnection(
            name="test_connection_1",
            type="AzureOpenAI",
            api_key="test_key",
            organization="test_org",
        )
        assert connection.to_execution_connection_dict() == {
            "module": "promptflow.connections",
            "secret_keys": ["api_key"],
            "type": "OpenAIConnection",
            "value": {"api_key": "test_key", "organization": "test_org"},
        }

    def test_validate_and_interactive_get_secrets(self):
        connection = CustomConnection(
            name="test_connection", secrets={"key1": SCRUBBED_VALUE, "key2": ""}
        )
        with patch("getpass.getpass", new=lambda prompt: "test_value"):
            validate_and_interactive_get_secrets(connection)
        assert connection.secrets == {"key1": "test_value", "key2": "test_value"}
