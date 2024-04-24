import os
import pathlib

import pandas as pd
import pytest

from promptflow.evals.evaluate import evaluate
from promptflow.evals.evaluate._evaluate import _apply_column_mapping
from promptflow.evals.evaluators import F1ScoreEvaluator, GroundednessEvaluator


@pytest.fixture
def invalid_jsonl_file():
    data_path = os.path.join(pathlib.Path(__file__).parent.resolve(), "data")
    return os.path.join(data_path, "invalid_evaluate_test_data.jsonl")


@pytest.fixture
def missing_columns_jsonl_file():
    data_path = os.path.join(pathlib.Path(__file__).parent.resolve(), "data")
    return os.path.join(data_path, "missing_columns_evaluate_test_data.jsonl")


@pytest.mark.usefixtures("mock_model_config")
@pytest.mark.unittest
class TestEvaluate:
    def test_evaluate_missing_data(self, mock_model_config):
        with pytest.raises(ValueError) as exc_info:
            evaluate(evaluators={"g": GroundednessEvaluator(model_config=mock_model_config)})

        assert "data must be provided for evaluation." in exc_info.value.args[0]

    def test_evaluate_evaluators_not_a_dict(self, mock_model_config):
        with pytest.raises(ValueError) as exc_info:
            evaluate(
                data="data",
                evaluators=[GroundednessEvaluator(model_config=mock_model_config)],
            )

        assert "evaluators must be a dictionary." in exc_info.value.args[0]

    def test_evaluate_invalid_data(self, mock_model_config):
        with pytest.raises(ValueError) as exc_info:
            evaluate(
                data=123,
                evaluators={"g": GroundednessEvaluator(model_config=mock_model_config)},
            )

        assert "data must be a string." in exc_info.value.args[0]

    def test_evaluate_invalid_jsonl_data(self, mock_model_config, invalid_jsonl_file):
        with pytest.raises(ValueError) as exc_info:
            evaluate(
                data=invalid_jsonl_file,
                evaluators={"g": GroundednessEvaluator(model_config=mock_model_config)},
            )

        assert "Failed to load data from " in exc_info.value.args[0]
        assert "Please validate it is a valid jsonl data" in exc_info.value.args[0]

    def test_evaluate_missing_required_inputs(self, missing_columns_jsonl_file):
        with pytest.raises(ValueError) as exc_info:
            evaluate(data=missing_columns_jsonl_file, evaluators={"g": F1ScoreEvaluator()})

        assert "Missing required inputs for evaluator g : ['ground_truth']." in exc_info.value.args[0]

    def test_apply_column_mapping(self):
        json_data = [
            {
                "question": "How are you?",
                "ground_truth": "I'm fine",
            }
        ]
        inputs_mapping = {
            "question": "${data.question}",
            "answer": "${data.ground_truth}",
        }

        data_df = pd.DataFrame(json_data)
        new_data_df = _apply_column_mapping(data_df, inputs_mapping)

        assert "question" in new_data_df.columns
        assert "answer" in new_data_df.columns

        assert new_data_df["question"][0] == "How are you?"
        assert new_data_df["answer"][0] == "I'm fine"

    def test_evaluate_invalid_evaluator_config(self, mock_model_config):
        with pytest.raises(ValueError) as exc_info:
            evaluate(
                data="data.jsonl",
                evaluators={"g": GroundednessEvaluator(model_config=mock_model_config)},
                evaluator_config={"g": {"question": "${foo.question}"}},
            )

        assert (
            "Unexpected references detected in 'evaluator_config'. Ensure only ${target.} and ${data.} are used."
            in exc_info.value.args[0]
        )
