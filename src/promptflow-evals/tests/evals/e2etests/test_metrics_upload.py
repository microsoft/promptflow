import json
import logging
import os
import pathlib
import pytest

from unittest.mock import patch, MagicMock
from promptflow.evals.evaluate import _utils as ev_utils
from promptflow.evals.evaluate._eval_run import EvalRun
from promptflow.evals.evaluators._f1_score._f1_score import F1ScoreEvaluator
from promptflow.evals.evaluate._evaluate import evaluate
import shutil
from promptflow._sdk._constants import LOCAL_MGMT_DB_PATH


@pytest.fixture
def data_file():
    data_path = os.path.join(pathlib.Path(__file__).parent.resolve(), "data")
    return os.path.join(data_path, "evaluate_test_data.jsonl")


@pytest.fixture
def questions_answers_file():
    data_path = os.path.join(pathlib.Path(__file__).parent.resolve(), "data")
    return os.path.join(data_path, "questions_answers.jsonl")


@pytest.fixture
def questions_file():
    data_path = os.path.join(pathlib.Path(__file__).parent.resolve(), "data")
    return os.path.join(data_path, "questions.jsonl")


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


class FakeTemporaryDirectory:
    """The class to create the temporary directory with the deterministic name."""

    def __init__(self, tempfolder: str, name):
        self.folder = os.path.join(tempfolder, name)

    def __enter__(self):
        os.makedirs(self.folder, exist_ok=True)
        return self.folder

    def __exit__(self, *kwargs):
        shutil.rmtree(self.folder)


@pytest.mark.usefixtures("model_config", "recording_injection", "project_scope")
@pytest.mark.e2etest
class TestMetricsUpload(object):
    """End to end tests to check how the metrics were uploaded to cloud."""

    @pytest.mark.usefixtures("vcr_recording")
    def test_writing_to_run_history(self, setup_data, caplog):
        """Test logging data to RunHistory service."""
        logger = logging.getLogger(ev_utils.__name__)
        # All loggers, having promptflow. prefix will have "promptflow" logger
        # as a parent. This logger does not propagate the logs and cannot be
        # captured by caplog. Here we will skip this logger to capture logs.
        logger.parent = logging.root
        # Just for sanity check let us make sure that the logging actually works
        mock_response = MagicMock()
        mock_response.status_code = 418
        with patch('promptflow.evals.evaluate._eval_run.EvalRun.request_with_retry', return_value=mock_response):
            ev_utils._write_properties_to_run_history({'test': 42})
            assert any(lg_rec.levelno == logging.ERROR for lg_rec in caplog.records), 'The error log was not captured!'
        caplog.clear()
        ev_utils._write_properties_to_run_history({'test': 42})
        assert not any(lg_rec.levelno == logging.ERROR for lg_rec in caplog.records)

    @pytest.mark.usefixtures("vcr_recording")
    def test_logging_metrics(self, setup_data, caplog):
        """Test logging metrics."""
        logger = logging.getLogger(EvalRun.__module__)
        # All loggers, having promptflow. prefix will have "promptflow" logger
        # as a parent. This logger does not propagate the logs and cannot be
        # captured by caplog. Here we will skip this logger to capture logs.
        logger.parent = logging.root
        ev_run = EvalRun.get_instance()
        mock_response = MagicMock()
        mock_response.status_code = 418
        with patch('promptflow.evals.evaluate._eval_run.EvalRun.request_with_retry', return_value=mock_response):
            ev_run.log_metric('f1', 0.54)
            assert any(lg_rec.levelno == logging.ERROR for lg_rec in caplog.records), 'The error log was not captured!'
        caplog.clear()
        ev_run.log_metric('f1', 0.54)
        assert len(caplog.records) == 0 or not any(lg_rec.levelno == logging.ERROR for lg_rec in caplog.records)

    @pytest.mark.usefixtures("vcr_recording")
    def test_log_artifact(self, setup_data, caplog, tmp_path):
        """Test uploading artifact to the service."""
        logger = logging.getLogger(EvalRun.__module__)
        # All loggers, having promptflow. prefix will have "promptflow" logger
        # as a parent. This logger does not propagate the logs and cannot be
        # captured by caplog. Here we will skip this logger to capture logs.
        logger.parent = logging.root
        ev_run = EvalRun.get_instance()
        mock_response = MagicMock()
        mock_response.status_code = 418
        with open(os.path.join(tmp_path, 'test.json'), 'w') as fp:
            json.dump({'f1': 0.5}, fp)
        os.makedirs(os.path.join(tmp_path, 'internal_dir'), exist_ok=True)
        with open(os.path.join(tmp_path, 'internal_dir', 'test.json'), 'w') as fp:
            json.dump({'internal_f1': 0.6}, fp)
        with patch('promptflow.evals.evaluate._eval_run.EvalRun.request_with_retry', return_value=mock_response):
            ev_run.log_artifact(tmp_path)
            assert any(lg_rec.levelno == logging.ERROR for lg_rec in caplog.records), 'The error log was not captured!'
        caplog.clear()
        ev_run.log_artifact(tmp_path)
        assert len(caplog.records) == 0 or not any(lg_rec.levelno == logging.ERROR for lg_rec in caplog.records)

    @pytest.mark.usefixtures("vcr_recording")
    def test_e2e_run_target_fn(self, caplog, project_scope, questions_answers_file):
        """Test evaluation run logging."""
        # We cannot define target in this file as pytest will load
        # all modules in test folder and target_fn will be imported from the first
        # module named test_evaluate and it will be a different module in unit test
        # folder. By keeping function in separate file we guarantee, it will be loaded
        # from there.
        from .target_fn import target_fn

        f1_score_eval = F1ScoreEvaluator()
        # Runs are stored in the sqlite file locally,
        # when ran in recording we will break the SQL constraint.
        # Temporary back up file if it exists.
        # backup_path = str(LOCAL_MGMT_DB_PATH) + '_backup'
        # if os.path.isfile(LOCAL_MGMT_DB_PATH):
        #     if os.path.isfile(backup_path):
        #         # If we have the backup test was already ran, just remove file.
        #         os.remove(LOCAL_MGMT_DB_PATH)
        #     else:
        #         os.rename(LOCAL_MGMT_DB_PATH, backup_path)
        # run the evaluation with targets
        # try:
        with patch('promptflow._sdk.entities._run.Run._dump'):    
            evaluate(
                data=questions_answers_file,
                target=target_fn,
                evaluators={"f1": f1_score_eval},
                azure_ai_project=project_scope,
                _run_name='eval_test_run2'
            )
        # finally:
            pass
            # if os.path.isfile(backup_path):
            #     try:
            #         os.remove(LOCAL_MGMT_DB_PATH)
            #         os.rename(backup_path, LOCAL_MGMT_DB_PATH)
            #     except BaseException:
            #         # Promptflow service is blocking file from being deleted.
            #         pass
        # Check there are no errors in the log.
        error_messages = []
        if caplog.records:
            error_messages = [
                lg_rec.message for lg_rec in caplog.records if lg_rec.levelno == logging.ERROR and (
                    lg_rec.name == ev_utils.__name__ or lg_rec.name == EvalRun.__module__)]

        assert not error_messages, '\n'.join(error_messages)

    @pytest.mark.usefixtures("vcr_recording")
    def test_e2e_run(self, caplog, project_scope, questions_answers_file):
        """Test evaluation run logging."""
        # Make sure that the URL ending in TraceSessions is in the recording, it is not always being recorded.
        # To record this test please modify the YAML file. It is missing "mlFlowTrackingUri" property by default.
        # Search URIs: https://management.azure.com/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups
        # /00000/providers/Microsoft.MachineLearningServices/workspaces/00000
        # In the BLOB SAS URI change sktid to 00000000-0000-0000-0000-000000000000
        # Add the tracking URI to properties dictionary with the key "mlFlowTrackingUri":
        # azureml://eastus2.api.azureml.ms/mlflow/v1.0/subscriptions/00000000-0000-0000-0000-000000000000/
        # resourceGroups/00000000-0000-0000-0000-000000000000/providers/Microsoft.MachineLearningServices/
        # workspaces/00000
        f1_score_eval = F1ScoreEvaluator()
        evaluate(
            data=questions_answers_file,
            evaluators={"f1": f1_score_eval},
            azure_ai_project=project_scope
        )
        # Check there are no errors in the log.
        error_messages = []
        if caplog.records:
            error_messages = [
                lg_rec.message for lg_rec in caplog.records if lg_rec.levelno == logging.ERROR and (
                    lg_rec.name == ev_utils.__name__ or lg_rec.name == EvalRun.__module__)]

        assert not error_messages, '\n'.join(error_messages)
