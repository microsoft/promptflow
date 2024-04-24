# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import os
import pandas as pd
import pathlib
import pytest

from pandas.testing import assert_frame_equal

from promptflow.client import PFClient
from promptflow.evals.evaluate._evaluate import _apply_target_to_data, evaluate
from promptflow.evals.evaluators.f1_score import F1ScoreEvaluator


@pytest.fixture
def pf_client() -> PFClient:
    """The fixture, returning PRClient"""
    return PFClient()


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


@pytest.mark.unittest
class TestEvaluateUnittest:
    """Test various functions from evaluate."""

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

    def test_apply_target_to_data(self, pf_client, questions_file, questions_answers_file):
        """Test that target was applied correctly."""
        initial_data = pd.read_json(questions_file, lines=True)
        qa, qa_df, columns = _apply_target_to_data(_target_fn, questions_file, pf_client, initial_data)
        assert columns == {'answer'}
        results = pd.read_json(qa, lines=True)
        assert_frame_equal(qa_df, results, check_like=True)
        ground_truth = pd.read_json(questions_answers_file, lines=True)
        try:
            assert_frame_equal(results, ground_truth, check_like=True)
        finally:
            os.unlink(qa)
