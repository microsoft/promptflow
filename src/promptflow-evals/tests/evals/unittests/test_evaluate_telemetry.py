import json
import os
import pathlib
from typing import Callable, Dict, Optional
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from promptflow.client import load_flow
from promptflow.evals.evaluate._telemetry import log_evaluate_activity
from promptflow.evals.evaluators import F1ScoreEvaluator, HateUnfairnessEvaluator


def _add_nans(df, n, column_name):
    mask = np.full(df.shape[0], False)  # Start with an all False mask (no NaNs)
    mask[:n] = True  # Set the first 'n' values to True
    np.random.shuffle(mask)  # Shuffle to distribute the NaNs randomly

    # Apply the mask to assign NaNs in the DataFrame column
    df.loc[mask, column_name] = np.nan


def _get_file(name):
    """Get the file from the unittest data folder."""
    data_path = os.path.join(pathlib.Path(__file__).parent.resolve(), "data")
    return os.path.join(data_path, name)


def answer_length(answer):
    return len(answer)


@pytest.fixture
def mock_app_insight_logger():
    """Mock validate trace destination config to use in unit tests."""
    logger = MagicMock()
    logger.info = MagicMock()
    logger.error = MagicMock()
    with patch("promptflow._sdk._telemetry.telemetry.get_telemetry_logger", return_value=logger):
        yield logger


@log_evaluate_activity
def dummy_evaluate_function(
    *,
    evaluation_name: Optional[str] = None,
    target: Optional[Callable] = None,
    data: Optional[str] = None,
    evaluators: Optional[Dict[str, Callable]] = None,
    evaluator_config: Optional[Dict[str, Dict[str, str]]] = None,
    azure_ai_project: Optional[Dict] = None,
    output_path: Optional[str] = None,
    **kwargs,
):
    df = pd.read_json(data, lines=True)
    nan_count = kwargs.get("number_of_nans", 1)
    for evaluation_name, evaluator in evaluators.items():

        df[f"outputs.{evaluation_name}.score"] = np.random.randint(0, 100, df.shape[0])
        _add_nans(df, nan_count, f"outputs.{evaluation_name}.score")

        # Add a new column with random strings
        df[f"outputs.{evaluation_name}.reason"] = np.random.choice(["a", "b", "c", "d", "e"], df.shape[0])

    return {
        "rows": df.to_dict(orient="records"),
    }


class TestEvaluateTelemetry:
    def test_evaluators_telemetry(self, mock_app_insight_logger):
        f1_score = F1ScoreEvaluator()
        apology_dag = load_flow(os.path.join(pathlib.Path(__file__).parent.resolve(), "test_evaluators", "apology_dag"))
        apology_prompty = load_flow(
            os.path.join(
                pathlib.Path(__file__).parent.resolve(), "test_evaluators", "apology_prompty", "apology.prompty"
            )
        )

        data = _get_file("evaluate_test_data.jsonl")
        evaluators = {
            "f1_score": f1_score,
            "apology_dag": apology_dag,
            "apology_prompty": apology_prompty,
            "answer_length": answer_length,
        }

        dummy_evaluate_function(evaluators=evaluators, data=data, number_of_nans=1)

        evaluate_start_call = [
            call for call in mock_app_insight_logger.info.call_args_list if "pf.evals.evaluate.start" in call.args[0]
        ]
        evaluate_start_call_cd = evaluate_start_call[0].kwargs["extra"]["custom_dimensions"]

        evaluate_usage_info_call = [
            call
            for call in mock_app_insight_logger.info.call_args_list
            if "pf.evals.evaluate_usage_info.start" in call.args[0]
        ]
        evaluate_usage_info_call_cd = evaluate_usage_info_call[0].kwargs["extra"]["custom_dimensions"]

        assert mock_app_insight_logger.info.call_count == 4
        assert len(evaluate_start_call) == 1
        assert len(evaluate_usage_info_call) == 1

        # asserts for evaluate start activity
        assert evaluate_start_call_cd["track_in_cloud"] is False
        assert evaluate_start_call_cd["evaluate_target"] is False
        assert evaluate_start_call_cd["evaluator_config"] is False

        # asserts for evaluate usage info activity
        evaluators_info = json.loads(evaluate_usage_info_call_cd["evaluators_info"])
        assert len(evaluators_info) == 4
        for entry in evaluators_info:
            if entry["alias"] == "f1_score":
                assert entry["pf_type"] == "FlexFlow"
                assert entry["name"] == "F1ScoreEvaluator"
                assert entry["type"] == "built-in"
            if entry["alias"] == "apology_dag":
                assert entry["pf_type"] == "DagFlow"
                assert entry["name"] == "apology_dag"
                assert entry["type"] == "custom"
            if entry["alias"] == "apology_prompty":
                assert entry["pf_type"] == "Prompty"
                assert entry["name"] == "apology_prompty"
                assert entry["type"] == "custom"
            if entry["alias"] == "answer_length":
                assert entry["pf_type"] == "FlexFlow"
                assert entry["name"] == "answer_length"
                assert entry["type"] == "custom"

            assert entry["failed_rows"] == 1

    def test_evaluator_start_telemetry(
        self,
        mock_app_insight_logger,
        mock_project_scope,
        mock_trace_destination_to_cloud,
        mock_validate_trace_destination,
    ):
        hate_unfairness = HateUnfairnessEvaluator(project_scope=None)

        data = _get_file("evaluate_test_data.jsonl")
        evaluators = {
            "hate_unfairness": hate_unfairness,
        }

        dummy_evaluate_function(
            target=answer_length,
            evaluators=evaluators,
            data=data,
            number_of_nans=2,
            azure_ai_project=mock_project_scope,
            evaluator_config={"hate_unfairness": {"model_config": "test_config"}},
        )

        evaluate_start_call = [
            call for call in mock_app_insight_logger.info.call_args_list if "pf.evals.evaluate.start" in call.args[0]
        ]
        evaluate_start_call_cd = evaluate_start_call[0].kwargs["extra"]["custom_dimensions"]

        # asserts for evaluate start activity
        assert evaluate_start_call_cd["track_in_cloud"] is True
        assert evaluate_start_call_cd["evaluate_target"] is True
        assert evaluate_start_call_cd["evaluator_config"] is True
