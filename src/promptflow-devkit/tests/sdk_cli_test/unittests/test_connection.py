# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import os
from unittest.mock import patch

import mock
import pytest
from _constants import PROMPTFLOW_ROOT

from promptflow._cli._pf._connection import validate_and_interactive_get_secrets
from promptflow._sdk._constants import SCRUBBED_VALUE, CustomStrongTypeConnectionConfigs
from promptflow._sdk._errors import ConnectionClassNotFoundError, SDKError
from promptflow._sdk._load_functions import _load_env_to_connection
from promptflow._sdk.entities._connection import (
    AzureAIServicesConnection,
    AzureContentSafetyConnection,
    AzureOpenAIConnection,
    CognitiveSearchConnection,
    CustomConnection,
    FormRecognizerConnection,
    OpenAIConnection,
    QdrantConnection,
    SerpConnection,
    ServerlessConnection,
    WeaviateConnection,
    _Connection,
)
from promptflow._utils.yaml_utils import load_yaml
from promptflow.constants import ConnectionAuthMode
from promptflow.core._connection import RequiredEnvironmentVariablesNotSetError
from promptflow.exceptions import UserErrorException

TEST_ROOT = PROMPTFLOW_ROOT / "tests"
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
                    "resource_id": "mock_id",
                },
                {
                    "module": "promptflow.connections",
                    "type": "azure_open_ai",
                    "auth_mode": "key",
                },
            ),
            (
                "azure_openai_aad_connection.yaml",
                AzureOpenAIConnection,
                {
                    "name": "my_azure_open_ai_connection",
                    "api_type": "azure",
                    "api_version": "2023-07-01-preview",
                    "api_base": "aoai-api-endpoint",
                    "auth_mode": "meid_token",
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
                "openai_connection_base_url.yaml",
                OpenAIConnection,
                {
                    "name": "my_open_ai_connection",
                    "api_key": "<to-be-replaced>",
                    "organization": "org",
                    "base_url": "custom_base_url",
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
                    "auth_mode": "key",
                },
            ),
            (
                "cognitive_search_aad_connection.yaml",
                CognitiveSearchConnection,
                {
                    "name": "my_cognitive_search_connection",
                    "api_base": "endpoint",
                    "auth_mode": "meid_token",
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
            (
                "serverless_connection.yaml",
                ServerlessConnection,
                {
                    "name": "my_serverless_connection",
                    "api_key": "<to-be-replaced>",
                    "api_base": "https://mock.api.base",
                },
                {
                    "module": "promptflow.connections",
                    "type": "serverless",
                },
            ),
            (
                "azure_ai_services_connection.yaml",
                AzureAIServicesConnection,
                {
                    "name": "my_ai_services_connection",
                    "api_key": "<to-be-replaced>",
                    "endpoint": "endpoint",
                },
                {
                    "module": "promptflow.connections",
                    "type": "azure_ai_services",
                    "auth_mode": "key",
                },
            ),
            (
                "azure_ai_services_aad_connection.yaml",
                AzureAIServicesConnection,
                {
                    "name": "my_ai_services_connection",
                    "endpoint": "endpoint",
                    "auth_mode": "meid_token",
                },
                {
                    "module": "promptflow.connections",
                    "type": "azure_ai_services",
                },
            ),
        ],
    )
    def test_connection_load_dump(self, file_name, class_name, init_param, expected):
        conn = _Connection._load(data=load_yaml(CONNECTION_ROOT / file_name))
        expected = {**expected, **init_param}
        assert dict(conn._to_dict()) == expected
        assert class_name(**init_param)._to_dict() == expected

    @pytest.mark.parametrize(
        "file_name, error_cls, error_message",
        [
            (
                "invalid/azure_openai_missing_key.yaml",
                SDKError,
                "'api_key' is required for key auth mode connection.",
            )
        ],
    )
    def test_connection_load_bad_case(self, file_name, error_cls, error_message):
        with pytest.raises(error_cls) as e:
            _Connection._load(data=load_yaml(CONNECTION_ROOT / file_name))
        assert error_message in str(e.value)

    def test_connection_load_from_env(self):
        connection = _load_env_to_connection(source=CONNECTION_ROOT / ".env", params_override=[{"name": "env_conn"}])
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
  aaa: '******'
  ccc: '******'
"""
        )

    def test_connection_load_from_env_file_bad_case(self):
        # Test file not found
        with pytest.raises(UserErrorException) as e:
            _load_env_to_connection(source=CONNECTION_ROOT / "mock.env", params_override=[{"name": "env_conn"}])
        assert "not found" in str(e.value)
        # Test file empty
        with pytest.raises(Exception) as e:
            _load_env_to_connection(source=CONNECTION_ROOT / "empty.env", params_override=[{"name": "env_conn"}])
        assert "Load nothing" in str(e.value)

    def test_to_execution_connection_dict(self):
        # Assert custom connection build
        connection = CustomConnection(name="test_connection", configs={"a": "1"}, secrets={"b": "2"})
        assert connection._to_execution_connection_dict() == {
            "name": "test_connection",
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
        assert connection._to_execution_connection_dict() == {
            "name": "test_connection_1",
            "module": "promptflow.connections",
            "secret_keys": ["api_key"],
            "type": "AzureOpenAIConnection",
            "value": {
                "api_base": "test_base",
                "api_key": "test_key",
                "api_type": "azure",
                "api_version": "2023-07-01-preview",
                "auth_mode": ConnectionAuthMode.KEY,
            },
        }

        # Assert strong type - AzureOpenAI - aad
        connection = AzureOpenAIConnection(
            name="test_connection_1",
            type="AzureOpenAI",
            auth_mode=ConnectionAuthMode.MEID_TOKEN,
            api_base="test_base",
            api_type="azure",
            api_version="2023-07-01-preview",
        )
        assert connection._to_execution_connection_dict() == {
            "name": "test_connection_1",
            "module": "promptflow.connections",
            "secret_keys": [],
            "type": "AzureOpenAIConnection",
            "value": {
                "api_base": "test_base",
                "api_type": "azure",
                "api_version": "2023-07-01-preview",
                "auth_mode": ConnectionAuthMode.MEID_TOKEN,
            },
        }

        # Assert strong type - OpenAI
        connection = OpenAIConnection(
            name="test_connection_1",
            type="AzureOpenAI",
            api_key="test_key",
            organization="test_org",
        )
        assert connection._to_execution_connection_dict() == {
            "name": "test_connection_1",
            "module": "promptflow.connections",
            "secret_keys": ["api_key"],
            "type": "OpenAIConnection",
            "value": {"api_key": "test_key", "organization": "test_org"},
        }

    def test_validate_and_interactive_get_secrets(self):
        # Path 1: Create
        connection = CustomConnection(
            name="test_connection",
            secrets={"key1": SCRUBBED_VALUE, "key2": "", "key3": "<no-change>", "key4": "<user-input>", "key5": "**"},
        )
        with patch("promptflow._cli._pf._connection.get_secret_input", new=lambda prompt: "test_value"):
            validate_and_interactive_get_secrets(connection, is_update=False)
        assert connection.secrets == {
            "key1": "test_value",
            "key2": "test_value",
            "key3": "test_value",
            "key4": "test_value",
            "key5": "test_value",
        }
        # Path 2: Update
        # Scrubbed value will be filled in _validate_and_encrypt_secrets for update, so no changes here.
        connection = CustomConnection(
            name="test_connection",
            secrets={"key1": SCRUBBED_VALUE, "key2": "", "key3": "<no-change>", "key4": "<user-input>", "key5": "**"},
        )
        with patch("promptflow._cli._pf._connection.get_secret_input", new=lambda prompt: "test_value"):
            validate_and_interactive_get_secrets(connection, is_update=True)
        assert connection.secrets == {
            "key1": SCRUBBED_VALUE,
            "key2": "",
            "key3": "<no-change>",
            "key4": "test_value",
            "key5": "**",
        }

    def test_validate_and_encrypt_secrets(self):
        # Path 1: Create
        connection = CustomConnection(
            name="test_connection",
            secrets={"key1": SCRUBBED_VALUE, "key2": "", "key3": "<no-change>", "key4": "<user-input>", "key5": "**"},
        )
        with pytest.raises(Exception) as e:
            connection._validate_and_encrypt_secrets()
        assert "secrets ['key1', 'key2', 'key3', 'key4', 'key5'] value invalid, please fill them" in str(e.value)
        # Path 2: Update
        connection._secrets = {"key1": "val1", "key2": "val2", "key4": "val4", "key5": "*"}
        # raise error for key3 as original value missing.
        # raise error for key5 as original value still scrubbed.
        # raise error for key4 even if it was in _secrets, because it requires <user-input>.
        with pytest.raises(Exception) as e:
            connection._validate_and_encrypt_secrets()
        assert "secrets ['key3', 'key4', 'key5'] value invalid, please fill them" in str(e.value)

    def test_convert_to_custom_strong_type(self, install_custom_tool_pkg):
        module_name = "my_tool_package.tools.my_tool_2"
        custom_conn_type = "MyFirstConnection"
        import importlib

        module = importlib.import_module(module_name)
        # Connection created by custom strong type connection template for package tool
        connection = CustomConnection(
            name="test_connection",
            configs={
                "a": "1",
                CustomStrongTypeConnectionConfigs.PROMPTFLOW_MODULE_KEY: module_name,
                CustomStrongTypeConnectionConfigs.PROMPTFLOW_TYPE_KEY: custom_conn_type,
            },
            secrets={"b": "2"},
        )
        res = connection._convert_to_custom_strong_type()
        assert isinstance(res, module.MyFirstConnection)
        assert res.secrets == {"b": "2"}

        # Connection created by custom connection template for script tool
        connection = CustomConnection(name="test_connection", configs={"a": "1"}, secrets={"b": "2"})
        res = connection._convert_to_custom_strong_type(module=module, to_class=custom_conn_type)
        assert isinstance(res, module.MyFirstConnection)
        assert res.configs == {"a": "1"}

        # Connection created with custom connection type in portal for package tool
        connection._convert_to_custom_strong_type(module=module_name, to_class=custom_conn_type)
        assert isinstance(res, module.MyFirstConnection)
        assert res.configs == {"a": "1"}

        # Invalid module
        module_name = "not_existing_module"
        with pytest.raises(ModuleNotFoundError, match=r".*No module named 'not_existing_module'*"):
            connection._convert_to_custom_strong_type(module=module_name, to_class=custom_conn_type)

        module_name = None
        with pytest.raises(
            UserErrorException,
            match=r".*Failed to convert to custom strong type connection because of invalid module or class*",
        ):
            connection._convert_to_custom_strong_type(module=module_name, to_class=custom_conn_type)

        custom_conn_type = None
        with pytest.raises(
            UserErrorException,
            match=r".*Failed to convert to custom strong type connection because of invalid module or class*",
        ):
            connection._convert_to_custom_strong_type(module=module_name, to_class=custom_conn_type)

    def test_connection_from_env(self):
        with pytest.raises(RequiredEnvironmentVariablesNotSetError) as e:
            AzureOpenAIConnection.from_env()
        assert "to build AzureOpenAIConnection not set" in str(e.value)

        with pytest.raises(RequiredEnvironmentVariablesNotSetError) as e:
            OpenAIConnection.from_env()
        assert "to build OpenAIConnection not set" in str(e.value)

        # Happy path
        # AzureOpenAI
        with mock.patch.dict(
            os.environ,
            {
                "AZURE_OPENAI_ENDPOINT": "test_endpoint",
                "AZURE_OPENAI_API_KEY": "test_key",
                "OPENAI_API_VERSION": "2024-01-01-preview",
            },
        ):
            connection = AzureOpenAIConnection.from_env("test_connection")
            assert connection._to_dict() == {
                "name": "test_connection",
                "module": "promptflow.connections",
                "type": "azure_open_ai",
                "api_base": "test_endpoint",
                "api_key": "test_key",
                "api_type": "azure",
                "api_version": "2024-01-01-preview",
                "auth_mode": "key",
            }
        # OpenAI
        with mock.patch.dict(
            os.environ, {"OPENAI_API_KEY": "test_key", "OPENAI_BASE_URL": "test_base", "OPENAI_ORG_ID": "test_org"}
        ):
            connection = OpenAIConnection.from_env("test_connection")
            assert connection._to_dict() == {
                "name": "test_connection",
                "module": "promptflow.connections",
                "type": "open_ai",
                "api_key": "test_key",
                "organization": "test_org",
                "base_url": "test_base",
            }

    def test_convert_core_connection_to_sdk_connection(self):
        # Assert strong type
        from promptflow.connections import AzureOpenAIConnection as CoreAzureOpenAIConnection

        connection_args = {
            "name": "abc",
            "api_base": "abc",
            "auth_mode": "meid_token",
            "api_version": "2023-07-01-preview",
        }
        connection = CoreAzureOpenAIConnection(**connection_args)
        sdk_connection = _Connection._from_core_connection(connection)
        assert isinstance(sdk_connection, AzureOpenAIConnection)
        assert sdk_connection._to_dict() == {
            "module": "promptflow.connections",
            "type": "azure_open_ai",
            "api_type": "azure",
            **connection_args,
        }
        # Assert custom type
        from promptflow.connections import CustomConnection as CoreCustomConnection

        connection_args = {
            "name": "abc",
            "configs": {"a": "1"},
            "secrets": {"b": "2"},
        }
        connection = CoreCustomConnection(**connection_args)
        sdk_connection = _Connection._from_core_connection(connection)
        assert isinstance(sdk_connection, CustomConnection)
        assert sdk_connection._to_dict() == {"module": "promptflow.connections", "type": "custom", **connection_args}

        # Bad case
        connection = CoreCustomConnection(**connection_args)
        connection.type = "unknown"
        with pytest.raises(ConnectionClassNotFoundError):
            _Connection._from_core_connection(connection)
