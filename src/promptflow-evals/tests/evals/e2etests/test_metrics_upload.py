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
from promptflow.tracing import _start_trace

try:
    from promptflow.recording.record_mode import is_live
except ModuleNotFoundError:
    # The file is being imported by the local test
    pass


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
def tracking_uri(azure_ml_client, project_scope):
    return azure_ml_client.workspaces.get(project_scope["project_name"]).mlflow_tracking_uri


@pytest.mark.usefixtures("model_config", "recording_injection", "project_scope")
class TestMetricsUpload(object):
    """End to end tests to check how the metrics were uploaded to cloud."""

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

    @pytest.mark.azuretest
    @pytest.mark.usefixtures("vcr_recording")
    def test_writing_to_run_history(self, caplog, project_scope, azure_ml_client, tracking_uri):
        """Test logging data to RunHistory service."""
        logger = logging.getLogger(EvalRun.__module__)
        # All loggers, having promptflow. prefix will have "promptflow" logger
        # as a parent. This logger does not propagate the logs and cannot be
        # captured by caplog. Here we will skip this logger to capture logs.
        logger.parent = logging.root
        # Just for sanity check let us make sure that the logging actually works
        mock_response = MagicMock()
        mock_response.status_code = 418
        with EvalRun(
            run_name="test",
            tracking_uri=tracking_uri,
            subscription_id=project_scope["subscription_id"],
            group_name=project_scope["resource_group_name"],
            workspace_name=project_scope["project_name"],
            ml_client=azure_ml_client,
        ) as ev_run:
            with patch("promptflow.evals.evaluate._eval_run.EvalRun.request_with_retry", return_value=mock_response):
                ev_run.write_properties_to_run_history({"test": 42})
                assert any(
                    lg_rec.levelno == logging.ERROR for lg_rec in caplog.records
                ), "The error log was not captured!"
            caplog.clear()
            ev_run.write_properties_to_run_history({"test": 42})
        self._assert_no_errors_for_module(caplog.records, [EvalRun.__module__])

    @pytest.mark.azuretest
    @pytest.mark.usefixtures("vcr_recording")
    def test_logging_metrics(self, caplog, project_scope, azure_ml_client, tracking_uri):
        """Test logging metrics."""
        logger = logging.getLogger(EvalRun.__module__)
        # All loggers, having promptflow. prefix will have "promptflow" logger
        # as a parent. This logger does not propagate the logs and cannot be
        # captured by caplog. Here we will skip this logger to capture logs.
        logger.parent = logging.root
        with EvalRun(
            run_name="test",
            tracking_uri=tracking_uri,
            subscription_id=project_scope["subscription_id"],
            group_name=project_scope["resource_group_name"],
            workspace_name=project_scope["project_name"],
            ml_client=azure_ml_client,
        ) as ev_run:
            mock_response = MagicMock()
            mock_response.status_code = 418
            with patch("promptflow.evals.evaluate._eval_run.EvalRun.request_with_retry", return_value=mock_response):
                ev_run.log_metric("f1", 0.54)
                assert any(
                    lg_rec.levelno == logging.WARNING for lg_rec in caplog.records
                ), "The error log was not captured!"
            caplog.clear()
            ev_run.log_metric("f1", 0.54)
        self._assert_no_errors_for_module(caplog.records, EvalRun.__module__)

    @pytest.mark.azuretest
    @pytest.mark.usefixtures("vcr_recording")
    @pytest.mark.skipif(not is_live(), reason="This test fails in CI and needs to be investigate. See bug: 3415807")
    def test_log_artifact(self, project_scope, azure_ml_client, tracking_uri, caplog, tmp_path):
        """Test uploading artifact to the service."""
        logger = logging.getLogger(EvalRun.__module__)
        # All loggers, having promptflow. prefix will have "promptflow" logger
        # as a parent. This logger does not propagate the logs and cannot be
        # captured by caplog. Here we will skip this logger to capture logs.
        logger.parent = logging.root
        with EvalRun(
            run_name="test",
            tracking_uri=tracking_uri,
            subscription_id=project_scope["subscription_id"],
            group_name=project_scope["resource_group_name"],
            workspace_name=project_scope["project_name"],
            ml_client=azure_ml_client,
        ) as ev_run:
            mock_response = MagicMock()
            mock_response.status_code = 418
            with open(os.path.join(tmp_path, EvalRun.EVALUATION_ARTIFACT), "w") as fp:
                json.dump({"f1": 0.5}, fp)
            os.makedirs(os.path.join(tmp_path, "internal_dir"), exist_ok=True)
            with open(os.path.join(tmp_path, "internal_dir", "test.json"), "w") as fp:
                json.dump({"internal_f1": 0.6}, fp)
            with patch("promptflow.evals.evaluate._eval_run.EvalRun.request_with_retry", return_value=mock_response):
                ev_run.log_artifact(tmp_path)
                assert any(
                    lg_rec.levelno == logging.WARNING for lg_rec in caplog.records
                ), "The error log was not captured!"
            caplog.clear()
            ev_run.log_artifact(tmp_path)
        self._assert_no_errors_for_module(caplog.records, EvalRun.__module__)

    @pytest.mark.performance_test
    def test_e2e_run_target_fn(self, caplog, project_scope, questions_answers_file, monkeypatch):
        """Test evaluation run logging."""
        # Afer re-recording this test, please make sure, that the cassette contains the POST
        # request ending by 00000/rundata and it has status 200.
        # Also make sure that the cosmos request ending by workspaces/00000/TraceSessions
        # and log metric call anding on /mlflow/runs/log-metric are also present.
        # pytest-cov generates coverage files, which are being uploaded. When recording tests,
        # make sure to enable coverage, check that .coverage.sanitized-suffix is present
        # in the cassette.

        # We cannot define target in this file as pytest will load
        # all modules in test folder and target_fn will be imported from the first
        # module named test_evaluate and it will be a different module in unit test
        # folder. By keeping function in separate file we guarantee, it will be loaded
        # from there.
        logger = logging.getLogger(EvalRun.__module__)
        # Switch off tracing as it is running in the second thread, wile
        # thread pool executor is not compatible with VCR.py.
        if not is_live():
            monkeypatch.setattr(_start_trace, "_is_devkit_installed", lambda: False)
        # All loggers, having promptflow. prefix will have "promptflow" logger
        # as a parent. This logger does not propagate the logs and cannot be
        # captured by caplog. Here we will skip this logger to capture logs.
        logger.parent = logging.root
        from .target_fn import target_fn

        f1_score_eval = F1ScoreEvaluator()
        evaluate(
            data=questions_answers_file,
            target=target_fn,
            evaluators={"f1": f1_score_eval},
            azure_ai_project=project_scope,
        )
        self._assert_no_errors_for_module(caplog.records, (ev_utils.__name__, EvalRun.__module__))

    @pytest.mark.performance_test
    def test_e2e_run(self, caplog, project_scope, questions_answers_file, monkeypatch):
        """Test evaluation run logging."""
        # Afer re-recording this test, please make sure, that the cassette contains the POST
        # request ending by /BulkRuns/create.
        # Also make sure that the cosmos request ending by workspaces/00000/TraceSessions
        # is also present.
        # pytest-cov generates coverage files, which are being uploaded. When recording tests,
        # make sure to enable coverage, check that .coverage.sanitized-suffix is present
        # in the cassette.
        logger = logging.getLogger(EvalRun.__module__)
        # All loggers, having promptflow. prefix will have "promptflow" logger
        # as a parent. This logger does not propagate the logs and cannot be
        # captured by caplog. Here we will skip this logger to capture logs.
        logger.parent = logging.root
        # Switch off tracing as it is running in the second thread, wile
        # thread pool executor is not compatible with VCR.py.
        if not is_live():
            monkeypatch.setattr(_start_trace, "_is_devkit_installed", lambda: False)
        f1_score_eval = F1ScoreEvaluator()
        evaluate(
            data=questions_answers_file,
            evaluators={"f1": f1_score_eval},
            azure_ai_project=project_scope,
        )
        self._assert_no_errors_for_module(caplog.records, (ev_utils.__name__, EvalRun.__module__))
