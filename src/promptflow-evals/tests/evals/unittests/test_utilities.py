'''
Created on Jun 11, 2024

@author: nirovins
'''
import os
import pytest

from unittest.mock import patch

from promptflow.evals.evaluate import _utils


@pytest.fixture
def setup_data():
    """Clean up the environment variables"""
    yield
    os.environ[_utils.AZUREML_OBO_ENABLED] = ""
    os.environ[_utils.DEFAULT_IDENTITY_CLIENT_ID] = ""


@pytest.mark.unittest
class TestUtilities:
    """Tests for evaluations utilities."""

    def test_obo_credential(self, setup_data):
        """Test that we are getting OBO credentials when it is desired."""
        os.environ[_utils.AZUREML_OBO_ENABLED] = "1"
        with patch('promptflow.evals.evaluate._utils.AzureMLOnBehalfOfCredential') as mock_obo:
            _utils._get_credential()
        mock_obo.assert_called_once()

    def test_identity_client(self, setup_data):
        """Test identity client."""
        os.environ[_utils.DEFAULT_IDENTITY_CLIENT_ID] = "mock_client"
        with patch('promptflow.evals.evaluate._utils.ManagedIdentityCredential') as mock_client:
            _utils._get_credential()
        mock_client.assert_called_with(client_id="mock_client")

    def test_default_client(self):
        """Test defaut client is called."""
        with patch('promptflow.evals.evaluate._utils.DefaultAzureCredential') as mock_default:
            _utils._get_credential()
        mock_default.assert_called_once()

    def test_cli_client(self):
        """Test CLI client is being called."""
        with patch('promptflow.evals.evaluate._utils.DefaultAzureCredential', side_effect=Exception('mock')):
            with patch('promptflow.evals.evaluate._utils.AzureCliCredential') as mock_cli:
                _utils._get_credential()
        mock_cli.assert_called_once()

    def test_force_cli_client(self):
        """Test CLI client is being called."""
        with patch('promptflow.evals.evaluate._utils.DefaultAzureCredential') as default_cli:
            with patch('promptflow.evals.evaluate._utils.AzureCliCredential') as mock_cli:
                _utils._get_credential(force_cli=True)
        default_cli.assert_not_called()
        mock_cli.assert_called_once()
