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
from promptflow.evals.evaluate._eval_run import EvalRun, RunStatus


def generate_mock_token():
    expiration_time = time.time() + 3600  # 1 hour in the future
    return jwt.encode({"exp": expiration_time}, "secret", algorithm="HS256")


@pytest.mark.unittest
@patch.object(ArmTokenCache, "_fetch_token", return_value=generate_mock_token())
class TestEvalRun:
    """Unit tests for the eval-run object."""

    _MOCK_CREDS = dict(
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

    def _get_mock_create_resonse(self, status=200):
        """Return the mock create request"""
        mock_response = MagicMock()
        mock_response.status_code = status
        if status != 200:
            mock_response.text = lambda: "Mock error"
        else:
            mock_response.json.return_value = {
                "run": {"info": {"run_id": str(uuid4()), "experiment_id": str(uuid4()), "run_name": str(uuid4())}}
            }
        return mock_response

    def _get_mock_end_response(self, status=200):
        """Get the mock end run response."""
        mock_response = MagicMock()
        mock_response.status_code = status
        mock_response.text = lambda: "Everything good" if status == 200 else "Everything bad"
        return mock_response

    @pytest.mark.parametrize(
        "status,should_raise", [("KILLED", False), ("WRONG_STATUS", True), ("FINISHED", False), ("FAILED", False)]
    )
    def test_end_raises(self, token_mock, status, should_raise, caplog):
        """Test that end run raises exception if incorrect status is set."""
        with patch("promptflow.evals._http_utils.HttpPipeline.request", return_value=self._get_mock_create_resonse()):
            with EvalRun(run_name=None, **TestEvalRun._MOCK_CREDS) as run:
                if should_raise:
                    with pytest.raises(ValueError) as cm:
                        run._end_run(status)
                    assert status in cm.value.args[0]
                else:
                    run._end_run(status)
                    assert len(caplog.records) == 0

    def test_run_logs_if_terminated(self, token_mock, caplog):
        """Test that run warn user if we are trying to terminate it twice."""
        with patch("promptflow.evals._http_utils.HttpPipeline.request", return_value=self._get_mock_create_resonse()):
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
            run._start_run()
            run._end_run("KILLED")
            run._end_run("KILLED")
            assert len(caplog.records) == 1
            assert "Unable to stop run due to Run status=RunStatus.TERMINATED." in caplog.records[0].message

    def test_end_logs_if_fails(self, token_mock, caplog):
        """Test that if the terminal status setting was failed, it is logged."""
        with patch(
            "promptflow.evals._http_utils.HttpPipeline.request",
            side_effect=[self._get_mock_create_resonse(), self._get_mock_end_response(500)],
        ):
            logger = logging.getLogger(EvalRun.__module__)
            # All loggers, having promptflow. prefix will have "promptflow" logger
            # as a parent. This logger does not propagate the logs and cannot be
            # captured by caplog. Here we will skip this logger to capture logs.
            logger.parent = logging.root
            with EvalRun(
                run_name=None,
                tracking_uri="www.microsoft.com",
                subscription_id="mock",
                group_name="mock",
                workspace_name="mock",
                ml_client=MagicMock(),
            ):
                pass
            assert len(caplog.records) == 1
            assert "Unable to terminate the run." in caplog.records[0].message

    def test_start_run_fails(self, token_mock, caplog):
        """Test that there are log messges if run was not started."""
        mock_response_start = MagicMock()
        mock_response_start.status_code = 500
        mock_response_start.text = lambda: "Mock internal service error."
        with patch("promptflow.evals._http_utils.HttpPipeline.request", return_value=mock_response_start):
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
            run._start_run()
            assert len(caplog.records) == 1
            assert "500" in caplog.records[0].message
            assert mock_response_start.text() in caplog.records[0].message
            assert "The results will be saved locally" in caplog.records[0].message
            caplog.clear()
            # Log artifact
            run.log_artifact("test")
            assert len(caplog.records) == 1
            assert "Unable to log artifact due to Run status=RunStatus.BROKEN." in caplog.records[0].message
            caplog.clear()
            # Log metric
            run.log_metric("a", 42)
            assert len(caplog.records) == 1
            assert "Unable to log metric due to Run status=RunStatus.BROKEN." in caplog.records[0].message
            caplog.clear()
            # End run
            run._end_run("FINISHED")
            assert len(caplog.records) == 1
            assert "Unable to stop run due to Run status=RunStatus.BROKEN." in caplog.records[0].message
            caplog.clear()

    def test_run_name(self, token_mock):
        """Test that the run name is the same as ID if name is not given."""
        mock_response = self._get_mock_create_resonse()
        with patch("promptflow.evals._http_utils.HttpPipeline.request", return_value=mock_response):
            with EvalRun(
                run_name=None,
                tracking_uri="www.microsoft.com",
                subscription_id="mock",
                group_name="mock",
                workspace_name="mock",
                ml_client=MagicMock(),
            ) as run:
                pass
        assert run.info.run_id == mock_response.json.return_value["run"]["info"]["run_id"]
        assert run.info.experiment_id == mock_response.json.return_value["run"]["info"]["experiment_id"]
        assert run.info.run_name == mock_response.json.return_value["run"]["info"]["run_name"]

    def test_run_with_name(self, token_mock):
        """Test that the run name is not the same as id if it is given."""
        mock_response = self._get_mock_create_resonse()
        mock_response.json.return_value["run"]["info"]["run_name"] = "test"
        with patch("promptflow.evals._http_utils.HttpPipeline.request", return_value=mock_response):
            with EvalRun(
                run_name="test",
                tracking_uri="www.microsoft.com",
                subscription_id="mock",
                group_name="mock",
                workspace_name="mock",
                ml_client=MagicMock(),
            ) as run:
                pass
        assert run.info.run_id == mock_response.json.return_value["run"]["info"]["run_id"]
        assert run.info.experiment_id == mock_response.json.return_value["run"]["info"]["experiment_id"]
        assert run.info.run_name == "test"
        assert run.info.run_name != run.info.run_id

    def test_get_urls(self, token_mock):
        """Test getting url-s from eval run."""
        with patch("promptflow.evals._http_utils.HttpPipeline.request", return_value=self._get_mock_create_resonse()):
            with EvalRun(run_name="test", **TestEvalRun._MOCK_CREDS) as run:
                pass
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
        "log_function,expected_str", [("log_artifact", "register artifact"), ("log_metric", "save metrics")]
    )
    def test_log_artifacts_logs_error(self, token_mock, tmp_path, caplog, log_function, expected_str):
        """Test that the error is logged."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = lambda: "Mock not found error."
        if log_function == "log_artifact":
            with open(os.path.join(tmp_path, "test.json"), "w") as fp:
                json.dump({"f1": 0.5}, fp)

        with patch(
            "promptflow.evals._http_utils.HttpPipeline.request",
            side_effect=[
                self._get_mock_create_resonse(),
                mock_response,
                self._get_mock_end_response(),
            ],
        ):
            logger = logging.getLogger(EvalRun.__module__)
            # All loggers, having promptflow. prefix will have "promptflow" logger
            # as a parent. This logger does not propagate the logs and cannot be
            # captured by caplog. Here we will skip this logger to capture logs.
            logger.parent = logging.root
            with EvalRun(run_name="test", **TestEvalRun._MOCK_CREDS) as run:
                fn = getattr(run, log_function)
                if log_function == "log_artifact":
                    with open(os.path.join(tmp_path, EvalRun.EVALUATION_ARTIFACT), "w") as fp:
                        fp.write("42")
                    kwargs = {"artifact_folder": tmp_path}
                else:
                    kwargs = {"key": "f1", "value": 0.5}
                with patch("promptflow.evals.evaluate._eval_run.BlobServiceClient", return_value=MagicMock()):
                    fn(**kwargs)
        assert len(caplog.records) == 1
        assert mock_response.text() in caplog.records[0].message
        assert "404" in caplog.records[0].message
        assert expected_str in caplog.records[0].message

    @pytest.mark.parametrize(
        "dir_exists,dir_empty,expected_error",
        [
            (True, True, "The path to the artifact is empty."),
            (False, True, "The path to the artifact is either not a directory or does not exist."),
            (True, False, "The run results file was not found, skipping artifacts upload."),
        ],
    )
    def test_wrong_artifact_path(
        self,
        token_mock,
        tmp_path,
        caplog,
        dir_exists,
        dir_empty,
        expected_error,
    ):
        """Test that if artifact path is empty, or dies not exist we are logging the error."""
        with patch("promptflow.evals._http_utils.HttpPipeline.request", return_value=self._get_mock_create_resonse()):
            with EvalRun(run_name="test", **TestEvalRun._MOCK_CREDS) as run:
                logger = logging.getLogger(EvalRun.__module__)
                # All loggers, having promptflow. prefix will have "promptflow" logger
                # as a parent. This logger does not propagate the logs and cannot be
                # captured by caplog. Here we will skip this logger to capture logs.
                logger.parent = logging.root
                artifact_folder = tmp_path if dir_exists else "wrong_path_567"
                if not dir_empty:
                    with open(os.path.join(tmp_path, "test.txt"), "w") as fp:
                        fp.write("42")
                run.log_artifact(artifact_folder)
            assert len(caplog.records) == 1
            assert expected_error in caplog.records[0].message

    def test_log_metrics_and_instance_results_logs_error(self, token_mock, caplog):
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

    def test_run_broken_if_no_tracking_uri(self, token_mock, caplog):
        """Test that if no tracking URI is provirded, the run is being marked as broken."""
        logger = logging.getLogger(ev_utils.__name__)
        # All loggers, having promptflow. prefix will have "promptflow" logger
        # as a parent. This logger does not propagate the logs and cannot be
        # captured by caplog. Here we will skip this logger to capture logs.
        logger.parent = logging.root
        with EvalRun(
            run_name=None,
            tracking_uri=None,
            subscription_id="mock",
            group_name="mock",
            workspace_name="mock",
            ml_client=MagicMock(),
        ) as run:
            assert len(caplog.records) == 1
            assert "The results will be saved locally, but will not be logged to Azure." in caplog.records[0].message
            with patch("promptflow.evals.evaluate._eval_run.EvalRun.request_with_retry") as mock_request:
                run.log_artifact("mock_dir")
                run.log_metric("foo", 42)
                run.write_properties_to_run_history({"foo": "bar"})
            mock_request.assert_not_called()

    @pytest.mark.parametrize(
        "status_code,pf_run",
        [
            (401, False),
            (200, False),
            (401, True),
            (200, True),
        ],
    )
    def test_lifecycle(self, token_mock, status_code, pf_run):
        """Test the run statuses throughout its life cycle."""
        pf_run_mock = None
        if pf_run:
            pf_run_mock = MagicMock()
            pf_run_mock.name = "mock_pf_run"
            pf_run_mock._experiment_name = "mock_pf_experiment"
        with patch(
            "promptflow.evals._http_utils.HttpPipeline.request", return_value=self._get_mock_create_resonse(status_code)
        ):
            run = EvalRun(run_name="test", **TestEvalRun._MOCK_CREDS, promptflow_run=pf_run_mock)
            assert run.status == RunStatus.NOT_STARTED, f"Get {run.status}, expected {RunStatus.NOT_STARTED}"
            run._start_run()
            if status_code == 200 or pf_run:
                assert run.status == RunStatus.STARTED, f"Get {run.status}, expected {RunStatus.STARTED}"
            else:
                assert run.status == RunStatus.BROKEN, f"Get {run.status}, expected {RunStatus.BROKEN}"
            run._end_run("FINISHED")
            if status_code == 200 or pf_run:
                assert run.status == RunStatus.TERMINATED, f"Get {run.status}, expected {RunStatus.TERMINATED}"
            else:
                assert run.status == RunStatus.BROKEN, f"Get {run.status}, expected {RunStatus.BROKEN}"

    def test_local_lifecycle(self, token_mock):
        """Test that the local run have correct statuses."""
        run = EvalRun(
            run_name=None,
            tracking_uri=None,
            subscription_id="mock",
            group_name="mock",
            workspace_name="mock",
            ml_client=MagicMock(),
        )
        assert run.status == RunStatus.NOT_STARTED, f"Get {run.status}, expected {RunStatus.NOT_STARTED}"
        run._start_run()
        assert run.status == RunStatus.BROKEN, f"Get {run.status}, expected {RunStatus.BROKEN}"
        run._end_run("FINISHED")
        assert run.status == RunStatus.BROKEN, f"Get {run.status}, expected {RunStatus.BROKEN}"

    @pytest.mark.parametrize("status_code", [200, 401])
    def test_write_properties(self, token_mock, caplog, status_code):
        """Test writing properties to the evaluate run."""
        mock_write = MagicMock()
        mock_write.status_code = status_code
        mock_write.text = lambda: "Mock error"
        with patch(
            "promptflow.evals._http_utils.HttpPipeline.request",
            side_effect=[self._get_mock_create_resonse(), mock_write, self._get_mock_end_response()],
        ):
            with EvalRun(run_name="test", **TestEvalRun._MOCK_CREDS) as run:
                run.write_properties_to_run_history({"foo": "bar"})
        if status_code != 200:
            assert len(caplog.records) == 1
            assert "Fail writing properties" in caplog.records[0].message
            assert mock_write.text() in caplog.records[0].message
        else:
            assert len(caplog.records) == 0

    def test_write_properties_to_run_history_logs_error(self, token_mock, caplog):
        """Test that we are logging the error when there is no trace destination."""
        logger = logging.getLogger(EvalRun.__module__)
        # All loggers, having promptflow. prefix will have "promptflow" logger
        # as a parent. This logger does not propagate the logs and cannot be
        # captured by caplog. Here we will skip this logger to capture logs.
        logger.parent = logging.root
        with EvalRun(
            run_name=None,
            tracking_uri=None,
            subscription_id="mock",
            group_name="mock",
            workspace_name="mock",
            ml_client=MagicMock(),
        ) as run:
            run.write_properties_to_run_history({"foo": "bar"})
        assert len(caplog.records) == 3
        assert "tracking_uri was not provided," in caplog.records[0].message
        assert "Unable to write properties due to Run status=RunStatus.BROKEN." in caplog.records[1].message
        assert "Unable to stop run due to Run status=RunStatus.BROKEN." in caplog.records[2].message

    @pytest.mark.parametrize(
        "function_literal,args,expected_action",
        [
            ("write_properties_to_run_history", ({"foo": "bar"}), "write properties"),
            ("log_metric", ("foo", 42), "log metric"),
            ("log_artifact", ("mock_folder",), "log artifact"),
        ],
    )
    def test_logs_if_not_started(self, token_mock, caplog, function_literal, args, expected_action):
        """Test that all public functions are raising exception if run is not started."""
        logger = logging.getLogger(ev_utils.__name__)
        # All loggers, having promptflow. prefix will have "promptflow" logger
        # as a parent. This logger does not propagate the logs and cannot be
        # captured by caplog. Here we will skip this logger to capture logs.
        logger.parent = logging.root
        run = EvalRun(run_name=None, **TestEvalRun._MOCK_CREDS)
        getattr(run, function_literal)(*args)
        assert len(caplog.records) == 1
        assert expected_action in caplog.records[0].message, caplog.records[0].message
        assert (
            f"Unable to {expected_action} due to Run status=RunStatus.NOT_STARTED" in caplog.records[0].message
        ), caplog.records[0].message

    @pytest.mark.parametrize("status", [RunStatus.STARTED, RunStatus.BROKEN, RunStatus.TERMINATED])
    def test_starting_started_run(self, token_mock, status):
        """Test exception if the run was already started"""
        run = EvalRun(run_name=None, **TestEvalRun._MOCK_CREDS)
        with patch(
            "promptflow.evals._http_utils.HttpPipeline.request",
            return_value=self._get_mock_create_resonse(500 if status == RunStatus.BROKEN else 200),
        ):
            run._start_run()
            if status == RunStatus.TERMINATED:
                run._end_run("FINISHED")
        with pytest.raises(RuntimeError) as cm:
            run._start_run()
        assert f"Unable to start run due to Run status={status}" in cm.value.args[0], cm.value.args[0]
