from unittest.mock import patch

from promptflow._core.token_provider import AzureTokenProvider, COGNITIVE_SCOPE, SEARCH_SCOPE


def test_get_token_with_sovereign_credential():
    # use 3 with blocks to make it compatible with python 3.8
    with patch("azure.ai.ml._azure_environments._get_default_cloud_name") as mock_cloud_name:
        with patch("azure.ai.ml._azure_environments._get_cloud") as mock_cloud:
            with patch("azure.identity.DefaultAzureCredential") as mock_credential:
                mock_cloud_name.return_value = "AzureChinaCloud"
                cloud = mock_cloud.return_value
                cloud.get.return_value = "authority"
                mock_token = "mocked_token"
                mock_credential.return_value.get_token.return_value.token = mock_token

                token_provider = AzureTokenProvider()
                assert token_provider.get_token() == mock_token


def test_get_token_with_search_scope():
    with patch("azure.identity.DefaultAzureCredential") as mock_credential:
        mock_token = "mocked_search_token"
        mock_credential.return_value.get_token.return_value.token = mock_token

        token_provider = AzureTokenProvider()
        token = token_provider.get_token(SEARCH_SCOPE)
        assert token == mock_token
        mock_credential.return_value.get_token.assert_called_with(SEARCH_SCOPE)


def test_get_token_with_custom_scope():
    with patch("azure.identity.DefaultAzureCredential") as mock_credential:
        mock_token = "mocked_custom_token"
        mock_credential.return_value.get_token.return_value.token = mock_token

        token_provider = AzureTokenProvider()
        custom_scope = "https://custom.search.azure.com/.default"
        token = token_provider.get_token(custom_scope)
        assert token == mock_token
        mock_credential.return_value.get_token.assert_called_with(custom_scope)
