import logging
import pytest

from promptflow.evals.evaluate._eval_run import EvalRun
from promptflow.evals.evaluate._utils import _write_properties_to_run_history


@pytest.fixture
def setup_data(azure_pf_client, project_scope):
    run = EvalRun(
        run_name='test',
        tracking_uri=(
            'https://eastus2.api.azureml.ms/mlflow/v2.0'
            f'/subscriptions{project_scope["subscription_id"]}'
            f'/resourceGroups/{project_scope["resource_group_name"]}'
            '/providers/Microsoft.MachineLearningServices'
            f'/workspaces/{project_scope["project_name"]}'),
        subscription_id=project_scope["subscription_id"],
        group_name=project_scope["resource_group_name"],
        workspace_name=project_scope["project_name"],
        ml_client=azure_pf_client._ml_client
    )
    yield
    run.end_run("FINISHED")


@pytest.mark.usefixtures("model_config", "recording_injection", "project_scope")
@pytest.mark.e2etest
class TestMetricsUpload(object):
    """End to end tests to check how the metrics were uploaded to cloud."""

    def test_writing_to_run_history(self, setup_data, caplog):
        """Test logging data to RunHistory service."""
        logger = logging.getLogger(_write_properties_to_run_history.__module__)
        # All loggers, having promptflow. prefix will have "promptflow" logger
        # as a parent. This logger does not propagate the logs and cannot be
        # captured by caplog. Here we will skip this logger to capture logs.
        logger.parent = logging.root
        _write_properties_to_run_history({'test': 42})
        assert len(caplog.records) == 0, caplog.records[0].message

    # def test_logging_metrics(self, setup_data):
    #     """Test logging metrics."""
    #
    # def test_log_artifact(self, setup_data):
    #     """Test uploading artifact to the service."""
    #
    #
    # def test_e2e_run(self):
    #     """Test evaluation run logging."""
