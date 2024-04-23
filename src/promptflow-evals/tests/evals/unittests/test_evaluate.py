import os
import pathlib

import pandas as pd
import pytest

from pandas.testing import assert_frame_equal
from unittest.mock import patch

from promptflow.evals.evaluate import evaluate
from promptflow.evals.evaluate._evaluate import _apply_target_to_data
from promptflow.evals.evaluators import F1ScoreEvaluator, GroundednessEvaluator
from promptflow.evals.evaluate._utils import save_function_as_flow


@pytest.fixture
def invalid_jsonl_file():
    data_path = os.path.join(pathlib.Path(__file__).parent.resolve(), "data")
    return os.path.join(data_path, "invalid_evaluate_test_data.jsonl")


@pytest.fixture
def missing_columns_jsonl_file():
    data_path = os.path.join(pathlib.Path(__file__).parent.resolve(), "data")
    return os.path.join(data_path, "missing_columns_evaluate_test_data.jsonl")


@pytest.fixture
def questions_file():
    data_path = os.path.join(pathlib.Path(__file__).parent.resolve(), "data")
    return os.path.join(data_path, "questions.jsonl")


@pytest.fixture
def questions_wrong_file():
    data_path = os.path.join(pathlib.Path(__file__).parent.resolve(), "data")
    return os.path.join(data_path, "questions_wrong.jsonl")


@pytest.fixture
def questions_answers_file():
    data_path = os.path.join(pathlib.Path(__file__).parent.resolve(), "data")
    return os.path.join(data_path, "questions_answers.jsonl")


def _target_fn(question):
    """An example target function."""
    if 'LV-426' in question:
        return {'answer': 'There is nothing good there.'}
    if 'central heating' in question:
        return {'answer': 'There is no central heating on the streets today, but it will be, I promise.'}
    if 'strange' in question:
        return {'answer': 'The life is strange...'}


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

    def test_evaluate_missing_required_inputs_target(self, questions_wrong_file):
        with pytest.raises(ValueError) as exc_info:
            evaluate(data=questions_wrong_file,
                     evaluators={"g": F1ScoreEvaluator()},
                     target=_target_fn
                     )
        assert "Missing required inputs for target : ['question']." in exc_info.value.args[0]

    def test_wrong_target(self, questions_file):
        """Test error, when target function does not generate required column."""
        with pytest.raises(ValueError) as exc_info:
            # target_fn will generate the "answer", but not ground truth.
            evaluate(data=questions_file, evaluators={"g": F1ScoreEvaluator()}, target=_target_fn)

        assert "Missing required inputs for evaluator g : ['ground_truth']." in exc_info.value.args[0]

    @pytest.mark.parametrize('script_is_file', [True, False])
    def test_save_fun_as_flow(self, tmpdir, pf_client, script_is_file):
        """Test saving function as flow."""
        with patch('promptflow.evals.evaluate._utils.os') as mock_os:
            mock_os.path.isfile.return_value = script_is_file
            save_function_as_flow(_target_fn, tmpdir, pf_client)
        assert os.path.isfile(os.path.join(tmpdir, 'flow.flex.yaml'))

    def test_apply_target_to_data(self, pf_client, questions_file, questions_answers_file):
        """Test that target was applied correctly."""
        qa = _apply_target_to_data(_target_fn, questions_file, pf_client)
        results = pd.read_json(qa, lines=True)
        ground_truth = pd.read_json(questions_answers_file, lines=True)
        try:
            assert_frame_equal(results, ground_truth, check_like=True)
        finally:
            os.unlink(qa)
