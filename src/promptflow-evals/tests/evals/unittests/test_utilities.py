'''
Created on Jun 11, 2024

@author: nirovins
'''
import os
import pandas as pd
import pytest

from unittest.mock import patch

from promptflow.evals.evaluate import _utils
import logging
from promptflow.evals.evaluate._eval_run import EvalRun
from promptflow.evals.evaluate._utils import AzureMLWorkspaceTriad


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

    @pytest.mark.parametrize('err_type', [ImportError, ModuleNotFoundError])
    def test_ml_client_not_imported(self, err_type):
        """Test import of ml_client if it was notimported."""
        with patch('builtins.__import__', side_effect=err_type('Mock')):
            ws_triade, ml_client = _utils._get_ml_client("www.microsoft.com")
        assert ml_client is None
        assert ws_triade.subscription_id == ""
        assert ws_triade.resource_group_name == ""
        assert ws_triade.workspace_name == ""

    def test_log_no_ml_client_import(self, caplog):
        """Test logging if MLClient cannot be imported."""
        logger = logging.getLogger(EvalRun.__module__)
        # All loggers, having promptflow. prefix will have "promptflow" logger
        # as a parent. This logger does not propagate the logs and cannot be
        # captured by caplog. Here we will skip this logger to capture logs.
        logger.parent = logging.root
        results = pd.DataFrame({
            'question': ['What is in my pocket?'],
            'answer': ['I do not know.'],
            'ground_truth': ['The ring.'],
            'f1': [0.0]})
        with patch('promptflow.evals.evaluate._utils._get_ml_client', return_value=(
              AzureMLWorkspaceTriad("", "", ""), None)):
            _utils._log_metrics_and_instance_results(
                {'f1': 0.0},
                results,
                (
                    "azureml://subscriptions/0000-000-000-000/"
                    "resourceGroups/mock_group/providers/Microsoft.MachineLearningServices/"
                    "workspaces/mock_workspace"
                ),
                None, 'mock_eval')
        error_messages = [
            lg_rec.message
            for lg_rec in caplog.records
            if lg_rec.levelno == logging.ERROR and (lg_rec.name in EvalRun.__module__)
        ]
        assert len(error_messages) == 4
