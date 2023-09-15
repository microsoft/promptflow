import pytest
from azure.ai.ml._restclient.v2023_06_01_preview.models import WorkspaceConnectionPropertiesV2BasicResource

from promptflow.azure.operations._arm_connection_operations import ArmConnectionOperations


def build_from_data_and_assert(data, expected):
    obj = WorkspaceConnectionPropertiesV2BasicResource.deserialize(data)
    assert ArmConnectionOperations.build_connection_dict_from_rest_object("mock", obj) == expected


@pytest.mark.unittest
def test_build_azure_openai_connection_from_rest_object():
    # Test on ApiKey type with AzureOpenAI category
    data = {
        "id": "mock_id",
        "name": "azure_open_ai_connection",
        "type": "Microsoft.MachineLearningServices/workspaces/connections",
        "properties": {
            "authType": "ApiKey",
            "credentials": {"key": "***"},
            "category": "AzureOpenAI",
            "target": "https://gpt-test-eus.openai.azure.com/",
            "metadata": {
                "azureml.flow.connection_type": "AzureOpenAI",
                "azureml.flow.module": "promptflow.connections",
                "ApiType": "azure",
                "ApiVersion": "2023-07-01-preview",
            },
        },
    }
    expected = {
        "type": "AzureOpenAIConnection",
        "module": "promptflow.connections",
        "value": {
            "api_base": "https://gpt-test-eus.openai.azure.com/",
            "api_key": "***",
            "api_type": "azure",
            "api_version": "2023-07-01-preview",
        },
    }
    build_from_data_and_assert(data, expected)


@pytest.mark.unittest
def test_build_default_azure_openai_connection_missing_metadata():
    # Test on ApiKey type with AzureOpenAI category
    data = {
        "id": "mock_id",
        "name": "azure_open_ai_connection",
        "type": "Microsoft.MachineLearningServices/workspaces/connections",
        "properties": {
            "authType": "ApiKey",
            "credentials": {"key": "***"},
            "category": "AzureOpenAI",
            "target": "https://gpt-test-eus.openai.azure.com/",
            "metadata": {
                "ApiType": "azure",
                "ApiVersion": "2023-07-01-preview",
            },
        },
    }
    expected = {
        "type": "AzureOpenAIConnection",
        "module": "promptflow.connections",
        "value": {
            "api_base": "https://gpt-test-eus.openai.azure.com/",
            "api_key": "***",
            "api_type": "azure",
            "api_version": "2023-07-01-preview",
        },
    }
    build_from_data_and_assert(data, expected)


@pytest.mark.unittest
def test_build_custom_keys_connection_from_rest_object():
    # Test on CustomKeys type with CustomConnection category
    data = {
        "id": "mock_id",
        "name": "custom_connection",
        "type": "Microsoft.MachineLearningServices/workspaces/connections",
        "properties": {
            "authType": "CustomKeys",
            "credentials": {"keys": {"my_key1": "***", "my_key2": "***"}},
            "category": "CustomKeys",
            "target": "https://gpt-test-eus.openai.azure.com/",
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
        "value": {"my_key1": "***", "my_key2": "***", "general_key": "general_value"},
        "secret_keys": ["my_key1", "my_key2"],
    }
    build_from_data_and_assert(data, expected)


@pytest.mark.unittest
def test_build_cognitive_search_connection_from_rest_object():
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
        "value": {"api_key": "***", "api_base": "mock_target", "api_version": "2023-07-01-Preview"},
    }
    build_from_data_and_assert(data, expected)


@pytest.mark.unittest
def test_build_cognitive_service_category_connection_from_rest_object():
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
        "value": {"api_key": "***", "endpoint": "mock_target", "api_version": "2023-04-30-preview"},
    }
    build_from_data_and_assert(data, expected)


@pytest.mark.unittest
def test_build_connection_missing_metadata():
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
                "Kind": "Content Safety",
                "ApiVersion": "2023-04-30-preview",
            },
        },
    }
    with pytest.raises(Exception) as e:
        build_from_data_and_assert(data, {})
    assert "is not recognized in PromptFlow" in str(e.value)


@pytest.mark.unittest
def test_build_connection_unknown_category():
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
    assert "Unknown connection mock category Unknown" in str(e.value)
