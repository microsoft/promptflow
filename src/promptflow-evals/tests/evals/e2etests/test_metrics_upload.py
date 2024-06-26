import json
import logging
import os
import pathlib
from unittest.mock import MagicMock, patch

import pytest

from promptflow.evals.evaluate import _utils as ev_utils
from promptflow.evals.evaluate._eval_run import EvalRun
from promptflow.evals.evaluate._evaluate import evaluate
from promptflow.evals.evaluators._f1_score._f1_score import F1ScoreEvaluator
from promptflow.recording.record_mode import is_live


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
def setup_data(azure_ml_client, project_scope):
    tracking_uri = azure_ml_client.workspaces.get(project_scope["project_name"]).mlflow_tracking_uri
    run = EvalRun(
        run_name='test',
        tracking_uri=tracking_uri,
        subscription_id=project_scope["subscription_id"],
        group_name=project_scope["resource_group_name"],
        workspace_name=project_scope["project_name"],
        ml_client=azure_ml_client
    )
    yield
    run.end_run("FINISHED")


@pytest.mark.usefixtures("model_config", "recording_injection", "project_scope")
@pytest.mark.e2etest
class TestMetricsUpload(object):
    """End to end tests to check how the metrics were uploaded to cloud."""
    # Add the tracking URI to properties dictionary with the key "mlFlowTrackingUri":
    # azureml://weatua2.api.azureml.ms/mlflow/v1.0/subscriptions/00000000-0000-0000-0000-000000000000/
    # resourceGroups/00000000-0000-0000-0000-000000000000/providers/Microsoft.MachineLearningServices/
    # workspaces/00000
    # Replace wetus2 to region you are running experiment in.

    def _assert_no_errors_for_module(self, records, module_names):
        """Check there are no errors in the log."""
        error_messages = []
        if records:
            error_messages = [
                lg_rec.message
                for lg_rec in records
                if lg_rec.levelno == logging.WARNING and (lg_rec.name in module_names)
            ]
            assert not error_messages, "\n".join(error_messages)

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
        with patch("promptflow.evals.evaluate._eval_run.EvalRun.request_with_retry", return_value=mock_response):
            ev_utils._write_properties_to_run_history({"test": 42})
            assert any(lg_rec.levelno == logging.ERROR for lg_rec in caplog.records), "The error log was not captured!"
        caplog.clear()
        ev_utils._write_properties_to_run_history({"test": 42})
        self._assert_no_errors_for_module(caplog.records, [ev_utils.__name__])

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
        with patch("promptflow.evals.evaluate._eval_run.EvalRun.request_with_retry", return_value=mock_response):
            ev_run.log_metric("f1", 0.54)
            assert any(
                lg_rec.levelno == logging.WARNING for lg_rec in caplog.records), "The error log was not captured!"
        caplog.clear()
        ev_run.log_metric("f1", 0.54)
        self._assert_no_errors_for_module(caplog.records, EvalRun.__module__)

    @pytest.mark.usefixtures("vcr_recording")
    def test_log_artifact(self, setup_data, caplog, tmp_path):
        """Test uploading artifact to the service."""
        # After re recording this test please replace sktid by
        # 00000000-0000-0000-0000-000000000000 in the request
        # with body: '{"f1": 0.5}' and body: '{"internal_f1": 0.6}'
        logger = logging.getLogger(EvalRun.__module__)
        # All loggers, having promptflow. prefix will have "promptflow" logger
        # as a parent. This logger does not propagate the logs and cannot be
        # captured by caplog. Here we will skip this logger to capture logs.
        logger.parent = logging.root
        ev_run = EvalRun.get_instance()
        mock_response = MagicMock()
        mock_response.status_code = 418
        with open(os.path.join(tmp_path, EvalRun.EVALUATION_ARTIFACT), 'w') as fp:
            json.dump({'f1': 0.5}, fp)
        os.makedirs(os.path.join(tmp_path, 'internal_dir'), exist_ok=True)
        with open(os.path.join(tmp_path, 'internal_dir', 'test.json'), 'w') as fp:
            json.dump({'internal_f1': 0.6}, fp)
        with patch('promptflow.evals.evaluate._eval_run.EvalRun.request_with_retry', return_value=mock_response):
            ev_run.log_artifact(tmp_path)
            assert any(
                lg_rec.levelno == logging.WARNING for lg_rec in caplog.records), "The error log was not captured!"
        caplog.clear()
        ev_run.log_artifact(tmp_path)
        self._assert_no_errors_for_module(caplog.records, EvalRun.__module__)

    @pytest.mark.skipif(
        condition=not is_live(),
        reason="promptflow run create files with random names, which cannot be recorded. See work item 3305909."
    )
    @pytest.mark.usefixtures("vcr_recording")
    def test_e2e_run_target_fn(self, caplog, project_scope, questions_answers_file):
        """Test evaluation run logging."""
        # We cannot define target in this file as pytest will load
        # all modules in test folder and target_fn will be imported from the first
        # module named test_evaluate and it will be a different module in unit test
        # folder. By keeping function in separate file we guarantee, it will be loaded
        # from there.
        logger = logging.getLogger(EvalRun.__module__)
        # All loggers, having promptflow. prefix will have "promptflow" logger
        # as a parent. This logger does not propagate the logs and cannot be
        # captured by caplog. Here we will skip this logger to capture logs.
        logger.parent = logging.root
        from .target_fn import target_fn

        f1_score_eval = F1ScoreEvaluator()
        # We need the deterministic name of a run, however it cannot be recorded
        # into database more then once or the database may be non writable.
        # By this reason we will cancel writing to database by mocking it.
        # Please uncomment this line for the local tests
        # with patch('promptflow._sdk.entities._run.Run._dump'):
        evaluate(
            data=questions_answers_file,
            target=target_fn,
            evaluators={"f1": f1_score_eval},
            azure_ai_project=project_scope,
            # _run_name="eval_test_run2",
        )
        self._assert_no_errors_for_module(caplog.records, (ev_utils.__name__, EvalRun.__module__))

    @pytest.mark.skipif(
        condition=not is_live(),
        reason="promptflow run create files with random names, which cannot be recorded. See work item 3305909."
    )
    @pytest.mark.usefixtures("vcr_recording")
    def test_e2e_run(self, caplog, project_scope, questions_answers_file):
        """Test evaluation run logging."""
        # Make sure that the URL ending in TraceSessions is in the recording, it is not always being recorded.
        # To record this test please modify the YAML file. It is missing "mlFlowTrackingUri" property by default.
        # Search URIs: https://management.azure.com/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups
        # /00000/providers/Microsoft.MachineLearningServices/workspaces/00000
        # Add the tracking URI to properties dictionary with the key "mlFlowTrackingUri":
        # azureml://weatua2.api.azureml.ms/mlflow/v1.0/subscriptions/00000000-0000-0000-0000-000000000000/
        # resourceGroups/00000000-0000-0000-0000-000000000000/providers/Microsoft.MachineLearningServices/
        # workspaces/00000
        logger = logging.getLogger(EvalRun.__module__)
        # All loggers, having promptflow. prefix will have "promptflow" logger
        # as a parent. This logger does not propagate the logs and cannot be
        # captured by caplog. Here we will skip this logger to capture logs.
        logger.parent = logging.root
        f1_score_eval = F1ScoreEvaluator()
        # We need the deterministic name of a run, however it cannot be recorded
        # into database more then once or the database may be non writable.
        # By this reason we will cancel writing to database by mocking it.
        # Please uncomment this line for the local tests
        # with patch('promptflow._sdk.entities._run.Run._dump'):
        evaluate(data=questions_answers_file, evaluators={"f1": f1_score_eval}, azure_ai_project=project_scope,
                 _run_name="eval_test_run4",)
        self._assert_no_errors_for_module(caplog.records, (ev_utils.__name__, EvalRun.__module__))
