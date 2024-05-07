# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import copy

import pytest

from promptflow.constants import ConnectionAuthMode
from promptflow.core._connection_provider._models._models import (
    WorkspaceConnectionPropertiesV2BasicResource,
    WorkspaceConnectionPropertiesV2BasicResourceArmPaginatedResult,
)
from promptflow.core._connection_provider._workspace_connection_provider import WorkspaceConnectionProvider


def build_from_data_and_assert(data, expected):
    data = copy.deepcopy(data)
    obj = WorkspaceConnectionPropertiesV2BasicResource.deserialize(data)
    assert WorkspaceConnectionProvider.build_connection_dict_from_rest_object(data["name"], obj) == expected


@pytest.mark.unittest
class TestWorkspaceConnectionProvider:
    def test_build_azure_openai_connection_from_rest_object(self):
        # Test on ApiKey type with AzureOpenAI category
        data = {
            "id": "mock_id",
            "name": "azure_open_ai_connection",
            "type": "Microsoft.MachineLearningServices/workspaces/connections",
            "properties": {
                "authType": "ApiKey",
                "credentials": {"key": "***"},
                "category": "AzureOpenAI",
                "target": "<api-base>",
                "metadata": {
                    "azureml.flow.connection_type": "AzureOpenAI",
                    "azureml.flow.module": "promptflow.connections",
                    "apiType": "azure",
                    "ApiVersion": "2023-07-01-preview",
                    "ResourceId": "mock_id",
                },
            },
        }
        expected = {
            "type": "AzureOpenAIConnection",
            "module": "promptflow.connections",
            "name": "azure_open_ai_connection",
            "value": {
                "api_base": "<api-base>",
                "api_key": "***",
                "api_type": "azure",
                "api_version": "2023-07-01-preview",
                "resource_id": "mock_id",
                "auth_mode": "key",
            },
        }
        build_from_data_and_assert(data, expected)

    def test_build_legacy_openai_connection_from_rest_object(self):
        # Legacy OpenAI connection with type in metadata
        # Test this not convert to CustomConnection
        data = {
            "id": "mock_id",
            "name": "legacy_open_ai",
            "type": "Microsoft.MachineLearningServices/workspaces/connections",
            "properties": {
                "authType": "CustomKeys",
                "credentials": {"keys": {"api_key": "***"}},
                "category": "CustomKeys",
                "target": "<api-base>",
                "metadata": {
                    "azureml.flow.connection_type": "OpenAI",
                    "azureml.flow.module": "promptflow.connections",
                    "organization": "mock",
                },
            },
        }
        expected = {
            "type": "OpenAIConnection",
            "module": "promptflow.connections",
            "name": "legacy_open_ai",
            "value": {"api_key": "***", "organization": "mock"},
        }
        build_from_data_and_assert(data, expected)

    def test_build_strong_type_openai_connection_from_rest_object(self):
        data = {
            "id": "mock_id",
            "name": "test_new_openai",
            "type": "Microsoft.MachineLearningServices/workspaces/connections",
            "properties": {
                "authType": "ApiKey",
                "credentials": {"key": "mock_key"},
                "group": "AzureAI",
                "category": "OpenAI",
                "target": "mock_base",
                "sharedUserList": [],
                "metadata": {"Organization": "mock"},
            },
        }
        expected = {
            "type": "OpenAIConnection",
            "module": "promptflow.connections",
            "name": "test_new_openai",
            "value": {
                "api_key": "mock_key",
                "organization": "mock",
                "base_url": "mock_base",
            },
        }
        build_from_data_and_assert(data, expected)

    def test_build_strong_type_serp_connection_from_rest_object(self):
        data = {
            "id": "mock_id",
            "name": "test_new_serp",
            "type": "Microsoft.MachineLearningServices/workspaces/connections",
            "properties": {
                "authType": "ApiKey",
                "credentials": {"key": "mock"},
                "group": "AzureAI",
                "category": "Serp",
                "target": "_",
                "sharedUserList": [],
                "metadata": {},
            },
        }
        expected = {
            "type": "SerpConnection",
            "module": "promptflow.connections",
            "name": "test_new_serp",
            "value": {
                "api_key": "mock",
            },
        }
        build_from_data_and_assert(data, expected)

    def test_build_default_azure_openai_connection_missing_metadata(self):
        # Test on ApiKey type with AzureOpenAI category
        data = {
            "id": "mock_id",
            "name": "azure_open_ai_connection",
            "type": "Microsoft.MachineLearningServices/workspaces/connections",
            "properties": {
                "authType": "ApiKey",
                "credentials": {"key": "***"},
                "category": "AzureOpenAI",
                "target": "<api-base>",
                "metadata": {
                    # Missing ApiType and ApiVersion
                    # "ApiType": "azure",
                    # "ApiVersion": "2023-07-01-preview",
                },
            },
        }
        expected = {
            "type": "AzureOpenAIConnection",
            "module": "promptflow.connections",
            "name": "azure_open_ai_connection",
            "value": {
                "api_base": "<api-base>",
                "api_key": "***",
                "auth_mode": "key",
                # Assert below keys are filtered out
                # "api_type": None,
                # "api_version": None,
            },
        }
        build_from_data_and_assert(data, expected)

    def test_build_aad_azure_openai_from_rest_obj(self):
        # Test on AAD type with AzureOpenAI category
        data = {
            "id": "mock_id",
            "name": "test_aad_aoai",
            "type": "Microsoft.MachineLearningServices/workspaces/connections",
            "properties": {
                "authType": "AAD",
                "group": "AzureAI",
                "category": "AzureOpenAI",
                "target": "<api-base>",
                "metadata": {
                    "ApiType": "azure",
                    "ApiVersion": "2023-07-01-preview",
                    "DeploymentApiVersion": "2023-10-01-preview",
                },
            },
        }
        expected = {
            "type": "AzureOpenAIConnection",
            "module": "promptflow.connections",
            "name": "test_aad_aoai",
            "value": {
                "api_base": "<api-base>",
                "api_type": "azure",
                "api_version": "2023-07-01-preview",
                "auth_mode": ConnectionAuthMode.MEID_TOKEN,
            },
        }
        build_from_data_and_assert(data, expected)

    def test_build_custom_keys_connection_from_rest_object(self):
        # Test on CustomKeys type with CustomConnection category
        data = {
            "id": "mock_id",
            "name": "custom_connection",
            "type": "Microsoft.MachineLearningServices/workspaces/connections",
            "properties": {
                "authType": "CustomKeys",
                "credentials": {"keys": {"my_key1": "***", "my_key2": "***"}},
                "category": "CustomKeys",
                "target": "<api-base>",
                "metadata": {
                    "azureml.flow.connection_type": "Custom",
                    "azureml.flow.module": "promptflow.connections",
                    "general_key": "general_value",
                },
            },
        }
        expected = {
            "type": "CustomConnection",
            "module": "promptflow.connections",
            "name": "custom_connection",
            "value": {"my_key1": "***", "my_key2": "***", "general_key": "general_value"},
            "secret_keys": ["my_key1", "my_key2"],
        }
        build_from_data_and_assert(data, expected)

    def test_build_strong_type_custom_connection_from_rest_object(self):
        # Test on CustomKeys type without meta
        data = {
            "id": "mock_id",
            "name": "custom_connection",
            "type": "Microsoft.MachineLearningServices/workspaces/connections",
            "properties": {
                "authType": "CustomKeys",
                "credentials": {"keys": {"my_key1": "***", "my_key2": "***"}},
                "category": "CustomKeys",
                "target": "<api-base>",
                "metadata": {
                    "general_key": "general_value",
                },
            },
        }
        expected = {
            "type": "CustomConnection",
            "module": "promptflow.connections",
            "name": "custom_connection",
            "value": {"my_key1": "***", "my_key2": "***", "general_key": "general_value"},
            "secret_keys": ["my_key1", "my_key2"],
        }
        build_from_data_and_assert(data, expected)

    def test_build_cognitive_search_connection_from_rest_object(self):
        # Test on ApiKey type with CognitiveSearch category
        data = {
            "tags": None,
            "location": None,
            "id": "mock_id",
            "name": "test",
            "type": "Microsoft.MachineLearningServices/workspaces/connections",
            "properties": {
                "authType": "ApiKey",
                "credentials": {"key": "***"},
                "category": "CognitiveSearch",
                "expiryTime": None,
                "target": "mock_target",
                "metadata": {
                    "azureml.flow.connection_type": "CognitiveSearch",
                    "azureml.flow.module": "promptflow.connections",
                    "ApiVersion": "2023-07-01-Preview",
                },
            },
        }
        expected = {
            "type": "CognitiveSearchConnection",
            "module": "promptflow.connections",
            "name": "test",
            "value": {
                "api_key": "***",
                "api_base": "mock_target",
                "api_version": "2023-07-01-Preview",
                "auth_mode": "key",
            },
        }
        build_from_data_and_assert(data, expected)

    def test_build_cognitive_search_aad_connection_from_rest_object(self):
        # Test on AAD type with CognitiveSearch category
        data = {
            "tags": None,
            "location": None,
            "id": "mock_id",
            "name": "test",
            "type": "Microsoft.MachineLearningServices/workspaces/connections",
            "properties": {
                "authType": "AAD",
                "category": "CognitiveSearch",
                "expiryTime": None,
                "target": "mock_target",
                "metadata": {
                    "ApiVersion": "2023-07-01-Preview",
                },
            },
        }
        expected = {
            "type": "CognitiveSearchConnection",
            "module": "promptflow.connections",
            "name": "test",
            "value": {
                "api_base": "mock_target",
                "api_version": "2023-07-01-Preview",
                "auth_mode": "meid_token",
            },
        }
        build_from_data_and_assert(data, expected)

    def test_build_cognitive_service_category_connection_from_rest_object(self):
        # Test on Api type with CognitiveService category
        data = {
            "id": "mock_id",
            "name": "ACS_Connection",
            "type": "Microsoft.MachineLearningServices/workspaces/connections",
            "properties": {
                "authType": "ApiKey",
                "credentials": {"key": "***"},
                "category": "CognitiveService",
                "target": "mock_target",
                "metadata": {
                    "azureml.flow.connection_type": "AzureContentSafety",
                    "azureml.flow.module": "promptflow.connections",
                    "Kind": "Content Safety",
                    "ApiVersion": "2023-04-30-preview",
                },
            },
        }
        expected = {
            "type": "AzureContentSafetyConnection",
            "module": "promptflow.connections",
            "name": "ACS_Connection",
            "value": {
                "api_key": "***",
                "endpoint": "mock_target",
                "api_version": "2023-04-30-preview",
                "auth_mode": "key",
            },
        }
        build_from_data_and_assert(data, expected)

        # Test category + kind as connection type
        del data["properties"]["metadata"]["azureml.flow.connection_type"]
        build_from_data_and_assert(data, expected)

    def test_build_connection_missing_metadata(self):
        data = {
            "id": "mock_id",
            "name": "ACS_Connection",
            "type": "Microsoft.MachineLearningServices/workspaces/connections",
            "properties": {
                "authType": "ApiKey",
                "credentials": {"key": "***"},
                "category": "CognitiveService",
                "target": "mock_target",
                "metadata": {
                    "ApiVersion": "2023-04-30-preview",
                },
            },
        }
        with pytest.raises(Exception) as e:
            build_from_data_and_assert(data, {})
        assert "is not recognized in PromptFlow" in str(e.value)

    def test_build_connection_unknown_category(self):
        data = {
            "id": "mock_id",
            "name": "ACS_Connection",
            "type": "Microsoft.MachineLearningServices/workspaces/connections",
            "properties": {
                "authType": "ApiKey",
                "credentials": {"key": "***"},
                "category": "Unknown",
                "target": "mock_target",
                "metadata": {
                    "azureml.flow.connection_type": "AzureContentSafety",
                    "azureml.flow.module": "promptflow.connections",
                    "Kind": "Content Safety",
                    "ApiVersion": "2023-04-30-preview",
                },
            },
        }
        with pytest.raises(Exception) as e:
            build_from_data_and_assert(data, {})
        assert "Unknown connection ACS_Connection category Unknown" in str(e.value)

    def test_build_serverless_category_connection_from_rest_object(self):
        data = {
            "id": "mock_id",
            "name": "test_serverless_connection",
            "type": "Microsoft.MachineLearningServices/workspaces/connections",
            "properties": {
                "authType": "ApiKey",
                "credentials": {"key": "***"},
                "group": "AzureAI",
                "category": "Serverless",
                "expiryTime": None,
                "target": "mock_base",
                "sharedUserList": [],
                "metadata": {},
            },
        }
        expected = {
            "type": "ServerlessConnection",
            "module": "promptflow.connections",
            "name": "test_serverless_connection",
            "value": {"api_key": "***", "api_base": "mock_base", "auth_mode": "key"},
        }
        build_from_data_and_assert(data, expected)

    def test_build_ai_services_connection_from_rest_object(self):
        data = {
            "id": "mock_id",
            "name": "test",
            "type": "Microsoft.MachineLearningServices/workspaces/connections",
            "properties": {
                "authType": "ApiKey",
                "credentials": {"key": "***"},
                "group": "AzureAI",
                "category": "AIServices",
                "target": "mock_base",
                "sharedUserList": [],
                "metadata": {},
            },
        }
        expected = {
            "type": "AzureAIServicesConnection",
            "module": "promptflow.connections",
            "name": "test",
            "value": {"api_key": "***", "endpoint": "mock_base", "auth_mode": "key"},
        }
        build_from_data_and_assert(data, expected)

    def test_build_ai_services_aad_connection_from_rest_object(self):
        data = {
            "id": "mock_id",
            "name": "test",
            "type": "Microsoft.MachineLearningServices/workspaces/connections",
            "properties": {
                "authType": "AAD",
                "group": "AzureAI",
                "category": "AIServices",
                "target": "mock_base",
                "sharedUserList": [],
                "metadata": {},
            },
        }
        expected = {
            "type": "AzureAIServicesConnection",
            "module": "promptflow.connections",
            "name": "test",
            "value": {"endpoint": "mock_base", "auth_mode": "meid_token"},
        }
        build_from_data_and_assert(data, expected)

    def test_build_connection_list(self):
        data = {
            "value": [
                {
                    "tags": None,
                    "location": None,
                    "id": "mock_id",
                    "name": "azure_open_ai_connection",
                    "type": "Microsoft.MachineLearningServices/workspaces/connections",
                    "properties": {
                        "authType": "ApiKey",
                        "credentials": None,
                        "group": "AzureAI",
                        "category": "AzureOpenAI",
                        "expiryTime": None,
                        "target": "mock_target",
                        "createdByWorkspaceArmId": None,
                        "useWorkspaceManagedIdentity": None,
                        "isSharedToAll": None,
                        "sharedUserList": [],
                        "metadata": {
                            "azureml.flow.connection_type": "AzureOpenAI",
                            "azureml.flow.module": "promptflow.connections",
                            "ApiType": "azure",
                            "ApiVersion": "2023-07-01-preview",
                            "ResourceId": "mock_resource_id",
                            "DeploymentApiVersion": "2023-10-01-preview",
                        },
                    },
                    "systemData": {
                        "createdAt": "2023-05-22T07:33:16.1272283Z",
                        "createdBy": "mock@microsoft.com",
                        "createdByType": "User",
                        "lastModifiedAt": "2023-05-22T07:33:16.1272283Z",
                        "lastModifiedBy": "mock@microsoft.com",
                        "lastModifiedByType": "User",
                    },
                },
                {
                    "name": "test1",
                    "type": "Microsoft.MachineLearningServices/workspaces/connections",
                    "properties": {
                        "authType": "CustomKeys",
                        "credentials": None,
                        "group": "AzureAI",
                        "category": "CustomKeys",
                        "expiryTime": None,
                        "target": "_",
                        "metadata": {
                            "azureml.flow.connection_type": "Custom",
                            "azureml.flow.module": "promptflow.connections",
                        },
                    },
                },
                {
                    "name": "AmlRunbook_CogSearch",
                    "type": "Microsoft.MachineLearningServices/workspaces/connections",
                    "properties": {
                        "authType": "ApiKey",
                        "credentials": None,
                        "group": "AzureAI",
                        "category": "CognitiveSearch",
                        "target": "_",
                        "metadata": {
                            "azureml.flow.connection_type": "CognitiveSearch",
                            "azureml.flow.module": "promptflow.connections",
                            "ApiVersion": "2023-07-01-Preview",
                            "DeploymentApiVersion": "2023-11-01",
                        },
                    },
                },
            ]
        }

        data = copy.deepcopy(data)
        obj = WorkspaceConnectionPropertiesV2BasicResourceArmPaginatedResult.deserialize(data)
        result = [
            WorkspaceConnectionProvider.build_connection_dict_from_rest_object(conn.name, conn) for conn in obj.value
        ]
        expected = [
            {
                "type": "AzureOpenAIConnection",
                "module": "promptflow.connections",
                "name": "azure_open_ai_connection",
                "value": {
                    "api_base": "mock_target",
                    "api_type": "azure",
                    "api_version": "2023-07-01-preview",
                    "resource_id": "mock_resource_id",
                    "auth_mode": "key",
                },
            },
            {
                "type": "CustomConnection",
                "module": "promptflow.connections",
                "name": "test1",
                "value": {},
                "secret_keys": [],
            },
            {
                "type": "CognitiveSearchConnection",
                "module": "promptflow.connections",
                "name": "AmlRunbook_CogSearch",
                "value": {"api_base": "_", "api_version": "2023-07-01-Preview", "auth_mode": "key"},
            },
        ]
        assert result == expected
