import os
import pathlib

import numpy as np
import pandas as pd
import pytest

from promptflow.evals.evaluate import evaluate
from promptflow.evals.evaluators import F1ScoreEvaluator, GroundednessEvaluator


@pytest.fixture
def data_file():
    data_path = os.path.join(pathlib.Path(__file__).parent.resolve(), "data")
    return os.path.join(data_path, "evaluate_test_data.jsonl")


@pytest.fixture
def questions_file():
    data_path = os.path.join(pathlib.Path(__file__).parent.resolve(), "data")
    return os.path.join(data_path, "questions.jsonl")


@pytest.fixture
def data_file_for_column_mapping():
    data_path = os.path.join(pathlib.Path(__file__).parent.resolve(), "data")
    return os.path.join(data_path, "evaluate_test_data_for_column_mapping.jsonl")


def answer_evaluator(answer):
    return {"length": len(answer)}


@pytest.mark.usefixtures("model_config", "recording_injection", "data_file")
@pytest.mark.e2etest
class TestEvaluate:
    def test_groundedness_evaluator(self, model_config, data_file):
        # data
        input_data = pd.read_json(data_file, lines=True)

        groundedness_eval = GroundednessEvaluator(model_config)
        f1_score_eval = F1ScoreEvaluator()

        # run the evaluation
        result = evaluate(
            data=data_file,
            evaluators={"grounded": groundedness_eval, "f1_score": f1_score_eval},
        )

        row_result_df = pd.DataFrame(result["rows"])
        metrics = result["metrics"]

        # validate the results
        assert result is not None
        assert result["rows"] is not None
        assert row_result_df.shape[0] == len(input_data)

        assert "outputs.grounded.gpt_groundedness" in row_result_df.columns.to_list()
        assert "outputs.f1_score.f1_score" in row_result_df.columns.to_list()

        assert "grounded.gpt_groundedness" in metrics.keys()
        assert "f1_score.f1_score" in metrics.keys()

        assert metrics.get("grounded.gpt_groundedness") == np.nanmean(
            row_result_df["outputs.grounded.gpt_groundedness"]
        )
        assert metrics.get("f1_score.f1_score") == np.nanmean(row_result_df["outputs.f1_score.f1_score"])

        assert row_result_df["outputs.grounded.gpt_groundedness"][2] in [4, 5]
        assert row_result_df["outputs.f1_score.f1_score"][2] == 1

    def test_evaluate_python_function(self, data_file):
        # data
        input_data = pd.read_json(data_file, lines=True)

        # run the evaluation
        result = evaluate(
            data=data_file,
            evaluators={"answer": answer_evaluator},
        )

        row_result_df = pd.DataFrame(result["rows"])
        metrics = result["metrics"]

        # validate the results
        assert result is not None
        assert result["rows"] is not None
        assert row_result_df.shape[0] == len(input_data)

        assert "outputs.answer.length" in row_result_df.columns.to_list()
        assert "answer.length" in metrics.keys()
        assert metrics.get("answer.length") == np.nanmean(row_result_df["outputs.answer.length"])
        assert row_result_df["outputs.answer.length"][2] == 31

    def test_evaluate_with_target(self, questions_file):
        """Test evaluation with target function."""
        # We cannot define target in this file as pytest will load
        # all modules in test folder and target_fn will be imported from the first
        # module named test_evaluate and it will be a different module in unit test
        # folder. By keeping function in separate file we guarantee, it will be loaded
        # from there.
        from .function_test import target_fn

        f1_score_eval = F1ScoreEvaluator()
        # run the evaluation with targets
        result = evaluate(
            data=questions_file,
            target=target_fn,
            evaluators={"answer": answer_evaluator, "f1": f1_score_eval},
        )
        row_result_df = pd.DataFrame(result["rows"])
        assert "outputs.answer" in row_result_df.columns
        assert "outputs.answer.length" in row_result_df.columns
        assert list(row_result_df["outputs.answer.length"]) == [28, 76, 22]
        assert "outputs.f1.f1_score" in row_result_df.columns
        assert not any(np.isnan(f1) for f1 in row_result_df["outputs.f1.f1_score"])

    @pytest.mark.usefixtures("data_file_for_column_mapping")
    def test_evaluate_with_evaluator_config(self, data_file_for_column_mapping):
        # data
        input_data = pd.read_json(data_file_for_column_mapping, lines=True)
        f1_score_evaluator = F1ScoreEvaluator()

        # run the evaluation
        result = evaluate(
            data=data_file_for_column_mapping,
            evaluators={"f1_score": f1_score_evaluator, "answer": answer_evaluator},
            evaluator_config={
                "f1_score": {
                    "ground_truth": "${data.ground_truth}",
                    "answer": "${data.response}",
                },
                "answer": {
                    "answer": "${target.response}",
                },
            },
        )

        row_result_df = pd.DataFrame(result["rows"])
        metrics = result["metrics"]

        # validate the results
        assert result is not None
        assert result["rows"] is not None
        assert row_result_df.shape[0] == len(input_data)

        assert "outputs.answer.length" in row_result_df.columns.to_list()
        assert "outputs.f1_score.f1_score" in row_result_df.columns.to_list()

        assert "answer.length" in metrics.keys()
        assert "f1_score.f1_score" in metrics.keys()
