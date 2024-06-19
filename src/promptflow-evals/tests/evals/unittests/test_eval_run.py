import json
import logging
import os
import time
from unittest.mock import MagicMock, patch
from uuid import uuid4

import jwt
import pytest

import promptflow.evals.evaluate._utils as ev_utils
from promptflow.azure._utils._token_cache import ArmTokenCache
from promptflow.evals.evaluate._eval_run import EvalRun, Singleton


@pytest.fixture
def setup_data():
    """Make sure, we will destroy the EvalRun instance as it is singleton."""
    yield
    Singleton._instances.clear()


def generate_mock_token():
    expiration_time = time.time() + 3600  # 1 hour in the future
    return jwt.encode({"exp": expiration_time}, "secret", algorithm="HS256")


@pytest.mark.unittest
@patch.object(ArmTokenCache, "_fetch_token", return_value=generate_mock_token())
class TestEvalRun:
    """Unit tests for the eval-run object."""

    @pytest.mark.parametrize(
        "status,should_raise", [("KILLED", False), ("WRONG_STATUS", True), ("FINISHED", False), ("FAILED", False)]
    )
    def test_end_raises(self, token_mock, setup_data, status, should_raise, caplog):
        """Test that end run raises exception if incorrect status is set."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "run": {
                "info": {
                    "run_id": str(uuid4()),
                    "experiment_id": str(uuid4()),
                    "run_name": str(uuid4())
                }
            }
        }
        mock_session.request.return_value = mock_response
        with patch("promptflow.evals.evaluate._eval_run.requests.Session", return_value=mock_session):
            run = EvalRun(
                run_name=None,
                tracking_uri="www.microsoft.com",
                subscription_id="mock",
                group_name="mock",
                workspace_name="mock",
                ml_client=MagicMock(),
            )
            if should_raise:
                with pytest.raises(ValueError) as cm:
                    run.end_run(status)
                assert status in cm.value.args[0]
            else:
                run.end_run(status)
                assert len(caplog.records) == 0

    def test_run_logs_if_terminated(self, token_mock, setup_data, caplog):
        """Test that run warn user if we are trying to terminate it twice."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "run": {
                "info": {
                    "run_id": str(uuid4()),
                    "experiment_id": str(uuid4()),
                    "run_name": str(uuid4())
                }
            }
        }
        mock_session.request.return_value = mock_response
        with patch("promptflow.evals.evaluate._eval_run.requests.Session", return_value=mock_session):
            logger = logging.getLogger(EvalRun.__module__)
            # All loggers, having promptflow. prefix will have "promptflow" logger
            # as a parent. This logger does not propagate the logs and cannot be
            # captured by caplog. Here we will skip this logger to capture logs.
            logger.parent = logging.root
            run = EvalRun(
                run_name=None,
                tracking_uri="www.microsoft.com",
                subscription_id="mock",
                group_name="mock",
                workspace_name="mock",
                ml_client=MagicMock(),
            )
            run.end_run("KILLED")
            run.end_run("KILLED")
            assert len(caplog.records) == 1
            assert "Unable to stop run because it was already terminated." in caplog.records[0].message

    def test_end_logs_if_fails(self, token_mock, setup_data, caplog):
        """Test that if the terminal status setting was failed, it is logged."""
        mock_session = MagicMock()
        mock_response_start = MagicMock()
        mock_response_start.status_code = 200
        mock_response_start.json.return_value = {
            "run": {
                "info": {
                    "run_id": str(uuid4()),
                    "experiment_id": str(uuid4()),
                    "run_name": str(uuid4())
                }
            }
        }
        mock_response_end = MagicMock()
        mock_response_end.status_code = 500
        mock_session.request.side_effect = [mock_response_start, mock_response_end]
        with patch("promptflow.evals.evaluate._eval_run.requests.Session", return_value=mock_session):
            logger = logging.getLogger(EvalRun.__module__)
            # All loggers, having promptflow. prefix will have "promptflow" logger
            # as a parent. This logger does not propagate the logs and cannot be
            # captured by caplog. Here we will skip this logger to capture logs.
            logger.parent = logging.root
            run = EvalRun(
                run_name=None,
                tracking_uri="www.microsoft.com",
                subscription_id="mock",
                group_name="mock",
                workspace_name="mock",
                ml_client=MagicMock(),
            )
            run.end_run("FINISHED")
            assert len(caplog.records) == 1
            assert "Unable to terminate the run." in caplog.records[0].message

    def test_start_run_fails(self, token_mock, setup_data, caplog):
        """Test that there are log messges if run was not started."""
        mock_session = MagicMock()
        mock_response_start = MagicMock()
        mock_response_start.status_code = 500
        mock_response_start.text = "Mock internal service error."
        mock_session.request.return_value = mock_response_start
        with patch("promptflow.evals.evaluate._eval_run.requests.Session", return_value=mock_session):
            logger = logging.getLogger(EvalRun.__module__)
            # All loggers, having promptflow. prefix will have "promptflow" logger
            # as a parent. This logger does not propagate the logs and cannot be
            # captured by caplog. Here we will skip this logger to capture logs.
            logger.parent = logging.root
            run = EvalRun(
                run_name=None,
                tracking_uri="www.microsoft.com",
                subscription_id="mock",
                group_name="mock",
                workspace_name="mock",
                ml_client=MagicMock(),
            )
            assert len(caplog.records) == 1
            assert "500" in caplog.records[0].message
            assert mock_response_start.text in caplog.records[0].message
            assert "The results will be saved locally" in caplog.records[0].message
            caplog.clear()
            # Log artifact
            run.log_artifact("test")
            assert len(caplog.records) == 1
            assert "Unable to log artifact because the run failed to start." in caplog.records[0].message
            caplog.clear()
            # Log metric
            run.log_metric("a", 42)
            assert len(caplog.records) == 1
            assert "Unable to log metric because the run failed to start." in caplog.records[0].message
            caplog.clear()
            # End run
            run.end_run("FINISHED")
            assert len(caplog.records) == 1
            assert "Unable to stop run because the run failed to start." in caplog.records[0].message
            caplog.clear()

    @pytest.mark.parametrize("destroy_run,runs_are_the_same", [(False, True), (True, False)])
    @patch("promptflow.evals.evaluate._eval_run.requests.Session")
    def test_singleton(self, mock_session_cls, token_mock, setup_data, destroy_run, runs_are_the_same):
        """Test that the EvalRun is actually a singleton."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = [
            {
                "run": {
                    "info": {
                        "run_id": str(uuid4()),
                        "experiment_id": str(uuid4()),
                        "run_name": str(uuid4())
                    }
                }
            },
            {
                "run": {
                    "info": {
                        "run_id": str(uuid4()),
                        "experiment_id": str(uuid4()),
                        "run_name": str(uuid4())
                    }
                }
            },
        ]
        mock_session = MagicMock()
        mock_session.request.return_value = mock_response
        mock_session_cls.return_value = mock_session
        run = EvalRun(
            run_name="run",
            tracking_uri="www.microsoft.com",
            subscription_id="mock",
            group_name="mock",
            workspace_name="mock",
            ml_client=MagicMock(),
        )
        id1 = id(run)
        if destroy_run:
            run.end_run("FINISHED")
        id2 = id(
            EvalRun(
                run_name="run",
                tracking_uri="www.microsoft.com",
                subscription_id="mock",
                group_name="mock",
                workspace_name="mock",
                ml_client=MagicMock(),
            )
        )
        assert (id1 == id2) == runs_are_the_same

    @patch("promptflow.evals.evaluate._eval_run.requests.Session")
    def test_run_name(self, mock_session_cls, token_mock, setup_data):
        """Test that the run name is the same as ID if name is not given."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "run": {
                "info": {
                    "run_id": str(uuid4()),
                    "experiment_id": str(uuid4()),
                    "run_name": str(uuid4())
                }
            }
        }
        mock_session = MagicMock()
        mock_session.request.return_value = mock_response
        mock_session_cls.return_value = mock_session
        run = EvalRun(
            run_name=None,
            tracking_uri="www.microsoft.com",
            subscription_id="mock",
            group_name="mock",
            workspace_name="mock",
            ml_client=MagicMock(),
        )
        assert run.info.run_id == mock_response.json.return_value['run']['info']['run_id']
        assert run.info.experiment_id == mock_response.json.return_value[
            'run']['info']['experiment_id']
        assert run.info.run_name == mock_response.json.return_value['run']['info']["run_name"]

    @patch("promptflow.evals.evaluate._eval_run.requests.Session")
    def test_run_with_name(self, mock_session_cls, token_mock, setup_data):
        """Test that the run name is not the same as id if it is given."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "run": {
                "info": {
                    "run_id": str(uuid4()),
                    "experiment_id": str(uuid4()),
                    "run_name": 'test'
                }
            }
        }
        mock_session = MagicMock()
        mock_session.request.return_value = mock_response
        mock_session_cls.return_value = mock_session
        run = EvalRun(
            run_name="test",
            tracking_uri="www.microsoft.com",
            subscription_id="mock",
            group_name="mock",
            workspace_name="mock",
            ml_client=MagicMock(),
        )
        assert run.info.run_id == mock_response.json.return_value['run']['info']['run_id']
        assert run.info.experiment_id == mock_response.json.return_value[
            'run']['info']['experiment_id']
        assert run.info.run_name == 'test'
        assert run.info.run_name != run.info.run_id

    @patch("promptflow.evals.evaluate._eval_run.requests.Session")
    def test_get_urls(self, mock_session_cls, token_mock, setup_data):
        """Test getting url-s from eval run."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "run": {
                "info": {
                    "run_id": str(uuid4()),
                    "experiment_id": str(uuid4()),
                    "run_name": str(uuid4())
                }
            }
        }
        mock_session = MagicMock()
        mock_session.request.return_value = mock_response
        mock_session_cls.return_value = mock_session
        run = EvalRun(
            run_name="test",
            tracking_uri=(
                "https://region.api.azureml.ms/mlflow/v2.0/subscriptions"
                "/000000-0000-0000-0000-0000000/resourceGroups/mock-rg-region"
                "/providers/Microsoft.MachineLearningServices"
                "/workspaces/mock-ws-region"
            ),
            subscription_id="000000-0000-0000-0000-0000000",
            group_name="mock-rg-region",
            workspace_name="mock-ws-region",
            ml_client=MagicMock(),
        )
        assert run.get_run_history_uri() == (
            "https://region.api.azureml.ms/history/v1.0/subscriptions"
            "/000000-0000-0000-0000-0000000/resourceGroups/mock-rg-region"
            "/providers/Microsoft.MachineLearningServices"
            "/workspaces/mock-ws-region/experimentids/"
            f"{run.info.experiment_id}/runs/{run.info.run_id}"
        ), "Wrong RunHistory URL"
        assert run.get_artifacts_uri() == (
            "https://region.api.azureml.ms/history/v1.0/subscriptions"
            "/000000-0000-0000-0000-0000000/resourceGroups/mock-rg-region"
            "/providers/Microsoft.MachineLearningServices"
            "/workspaces/mock-ws-region/experimentids/"
            f"{run.info.experiment_id}/runs/{run.info.run_id}"
            "/artifacts/batch/metadata"
        ), "Wrong Artifacts URL"
        assert run.get_metrics_url() == (
            "https://region.api.azureml.ms/mlflow/v2.0/subscriptions"
            "/000000-0000-0000-0000-0000000/resourceGroups/mock-rg-region"
            "/providers/Microsoft.MachineLearningServices"
            "/workspaces/mock-ws-region/api/2.0/mlflow/runs/log-metric"
        ), "Wrong Metrics URL"

    @pytest.mark.parametrize(
        'log_function,expected_str',
        [
            ('log_artifact', 'register artifact'),
            ('log_metric', 'save metrics')
        ]
    )
    def test_log_artifacts_logs_error(self, token_mock, setup_data, tmp_path, caplog, log_function, expected_str):
        """Test that the error is logged."""
        mock_session = MagicMock()
        mock_create_response = MagicMock()
        mock_create_response.status_code = 200
        mock_create_response.json.return_value = {
            "run": {
                "info": {
                    "run_id": str(uuid4()),
                    "experiment_id": str(uuid4()),
                    "run_name": str(uuid4())
                }
            }
        }
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Mock not found error."

        if log_function == "log_artifact":
            with open(os.path.join(tmp_path, "test.json"), "w") as fp:
                json.dump({"f1": 0.5}, fp)
        mock_session.request.side_effect = [mock_create_response, mock_response]
        with patch("promptflow.evals.evaluate._eval_run.requests.Session", return_value=mock_session):
            run = EvalRun(
                run_name="test",
                tracking_uri=(
                    "https://region.api.azureml.ms/mlflow/v2.0/subscriptions"
                    "/000000-0000-0000-0000-0000000/resourceGroups/mock-rg-region"
                    "/providers/Microsoft.MachineLearningServices"
                    "/workspaces/mock-ws-region"
                ),
                subscription_id="000000-0000-0000-0000-0000000",
                group_name="mock-rg-region",
                workspace_name="mock-ws-region",
                ml_client=MagicMock(),
            )

            logger = logging.getLogger(EvalRun.__module__)
            # All loggers, having promptflow. prefix will have "promptflow" logger
            # as a parent. This logger does not propagate the logs and cannot be
            # captured by caplog. Here we will skip this logger to capture logs.
            logger.parent = logging.root
            fn = getattr(run, log_function)
            if log_function == 'log_artifact':
                with open(os.path.join(tmp_path, EvalRun.EVALUATION_ARTIFACT), 'w') as fp:
                    fp.write('42')
                kwargs = {'artifact_folder': tmp_path}
            else:
                kwargs = {'key': 'f1', 'value': 0.5}
            with patch('promptflow.evals.evaluate._eval_run.BlobServiceClient', return_value=MagicMock()):
                fn(**kwargs)
        assert len(caplog.records) == 1
        assert mock_response.text in caplog.records[0].message
        assert "404" in caplog.records[0].message
        assert expected_str in caplog.records[0].message

    @pytest.mark.parametrize(
        'dir_exists,dir_empty,expected_error', [
            (True, True, "The path to the artifact is empty."),
            (False, True, "The path to the artifact is either not a directory or does not exist."),
            (True, False, "The run results file was not found, skipping artifacts upload.")
        ]
    )
    def test_wrong_artifact_path(self, token_mock, tmp_path, caplog, dir_exists, dir_empty, expected_error, setup_data):
        """Test that if artifact path is empty, or dies not exist we are logging the error."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "run": {
                "info": {
                    "run_id": str(uuid4()),
                    "experiment_id": str(uuid4()),
                    "run_name": str(uuid4())
                }
            }
        }
        mock_session = MagicMock()
        mock_session.request.return_value = mock_response
        with patch("promptflow.evals.evaluate._eval_run.requests.Session", return_value=mock_session):
            run = EvalRun(
                run_name="test",
                tracking_uri=(
                    "https://region.api.azureml.ms/mlflow/v2.0/subscriptions"
                    "/000000-0000-0000-0000-0000000/resourceGroups/mock-rg-region"
                    "/providers/Microsoft.MachineLearningServices"
                    "/workspaces/mock-ws-region"
                ),
                subscription_id="000000-0000-0000-0000-0000000",
                group_name="mock-rg-region",
                workspace_name="mock-ws-region",
                ml_client=MagicMock(),
            )
            logger = logging.getLogger(EvalRun.__module__)
            # All loggers, having promptflow. prefix will have "promptflow" logger
            # as a parent. This logger does not propagate the logs and cannot be
            # captured by caplog. Here we will skip this logger to capture logs.
            logger.parent = logging.root
            artifact_folder = tmp_path if dir_exists else "wrong_path_567"
            if not dir_empty:
                with open(os.path.join(tmp_path, "test.txt"), 'w') as fp:
                    fp.write("42")
            run.log_artifact(artifact_folder)
            assert len(caplog.records) == 1
            assert expected_error in caplog.records[0].message

    def test_log_metrics_and_instance_results_logs_error(self, token_mock, caplog, setup_data):
        """Test that we are logging the error when there is no trace destination."""
        logger = logging.getLogger(ev_utils.__name__)
        # All loggers, having promptflow. prefix will have "promptflow" logger
        # as a parent. This logger does not propagate the logs and cannot be
        # captured by caplog. Here we will skip this logger to capture logs.
        logger.parent = logging.root
        ev_utils._log_metrics_and_instance_results(
            metrics=None,
            instance_results=None,
            trace_destination=None,
            run=None,
            evaluation_name=None,
        )
        assert len(caplog.records) == 1
        assert "Unable to log traces as trace destination was not defined." in caplog.records[0].message

    def test_run_broken_if_no_tracking_uri(self, setup_data, caplog):
        """Test that if no tracking URI is provirded, the run is being marked as broken."""
        logger = logging.getLogger(ev_utils.__name__)
        # All loggers, having promptflow. prefix will have "promptflow" logger
        # as a parent. This logger does not propagate the logs and cannot be
        # captured by caplog. Here we will skip this logger to capture logs.
        logger.parent = logging.root
        run = EvalRun(
            run_name=None,
            tracking_uri=None,
            subscription_id='mock',
            group_name='mock',
            workspace_name='mock',
            ml_client=MagicMock()
        )
        assert len(caplog.records) == 1
        assert "The results will be saved locally, but will not be logged to Azure." in caplog.records[0].message
        with patch('promptflow.evals.evaluate._eval_run.EvalRun.request_with_retry') as mock_request:
            run.log_artifact('mock_dir')
            run.log_metric('foo', 42)
        mock_request.assert_not_called()
