import json
import os
import pathlib
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from promptflow.client import PFClient
from promptflow.evals._constants import DEFAULT_EVALUATION_RESULTS_FILE_NAME
from promptflow.evals.evaluate import evaluate
from promptflow.evals.evaluate._evaluate import _apply_target_to_data, _rename_columns_conditionally
from promptflow.evals.evaluate._utils import _apply_column_mapping, _trace_destination_from_project_scope
from promptflow.evals.evaluators import F1ScoreEvaluator, GroundednessEvaluator


def _get_file(name):
    """Get the file from the unittest data folder."""
    data_path = os.path.join(pathlib.Path(__file__).parent.resolve(), "data")
    return os.path.join(data_path, name)


@pytest.fixture
def invalid_jsonl_file():
    return _get_file("invalid_evaluate_test_data.jsonl")


@pytest.fixture
def missing_columns_jsonl_file():
    return _get_file("missing_columns_evaluate_test_data.jsonl")


@pytest.fixture
def evaluate_test_data_jsonl_file():
    return _get_file("evaluate_test_data.jsonl")


@pytest.fixture
def pf_client() -> PFClient:
    """The fixture, returning PRClient"""
    return PFClient()


@pytest.fixture
def questions_file():
    return _get_file("questions.jsonl")


@pytest.fixture
def questions_wrong_file():
    return _get_file("questions_wrong.jsonl")


@pytest.fixture
def questions_answers_file():
    return _get_file("questions_answers.jsonl")


def _target_fn(question):
    """An example target function."""
    if "LV-426" in question:
        return {"answer": "There is nothing good there."}
    if "central heating" in question:
        return {"answer": "There is no central heating on the streets today, but it will be, I promise."}
    if "strange" in question:
        return {"answer": "The life is strange..."}


def _yeti_evaluator(question, answer):
    if "yeti" in question.lower():
        raise ValueError("Do not ask about Yeti!")
    return {"result": len(answer)}


def _target_fn2(question):
    response = _target_fn(question)
    response["question"] = f"The question is as follows: {question}"
    return response


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
            evaluate(data=questions_wrong_file, evaluators={"g": F1ScoreEvaluator()}, target=_target_fn)
        assert "Missing required inputs for target : ['question']." in exc_info.value.args[0]

    def test_wrong_target(self, questions_file):
        """Test error, when target function does not generate required column."""
        with pytest.raises(ValueError) as exc_info:
            # target_fn will generate the "answer", but not ground truth.
            evaluate(data=questions_file, evaluators={"g": F1ScoreEvaluator()}, target=_target_fn)

        assert "Missing required inputs for evaluator g : ['ground_truth']." in exc_info.value.args[0]

    def test_target_raises_on_outputs(self):
        """Test we are raising exception if the output is column is present in the input."""
        data = _get_file("questions_answers_outputs.jsonl")
        with pytest.raises(ValueError) as cm:
            evaluate(
                data=data,
                target=_target_fn,
                evaluators={"g": F1ScoreEvaluator()},
            )
        assert 'The column cannot start from "__outputs." if target was defined.' in cm.value.args[0]

    @pytest.mark.parametrize(
        "input_file,out_file,expected_columns,fun",
        [
            ("questions.jsonl", "questions_answers.jsonl", {"answer"}, _target_fn),
            (
                "questions_ground_truth.jsonl",
                "questions_answers_ground_truth.jsonl",
                {"answer", "question"},
                _target_fn2,
            ),
        ],
    )
    def test_apply_target_to_data(self, pf_client, input_file, out_file, expected_columns, fun):
        """Test that target was applied correctly."""
        data = _get_file(input_file)
        expexted_out = _get_file(out_file)
        initial_data = pd.read_json(data, lines=True)
        qa_df, columns, _ = _apply_target_to_data(fun, data, pf_client, initial_data)
        assert columns == expected_columns
        ground_truth = pd.read_json(expexted_out, lines=True)
        assert_frame_equal(qa_df, ground_truth, check_like=True)

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

    @pytest.mark.parametrize(
        "json_data,inputs_mapping,answer",
        [
            (
                [
                    {
                        "question": "How are you?",
                        "__outputs.answer": "I'm fine",
                    }
                ],
                {
                    "question": "${data.question}",
                    "answer": "${run.outputs.answer}",
                },
                "I'm fine",
            ),
            (
                [
                    {
                        "question": "How are you?",
                        "answer": "I'm fine",
                        "__outputs.answer": "I'm great",
                    }
                ],
                {
                    "question": "${data.question}",
                    "answer": "${run.outputs.answer}",
                },
                "I'm great",
            ),
            (
                [
                    {
                        "question": "How are you?",
                        "answer": "I'm fine",
                        "__outputs.answer": "I'm great",
                    }
                ],
                {
                    "question": "${data.question}",
                    "answer": "${data.answer}",
                },
                "I'm fine",
            ),
            (
                [
                    {
                        "question": "How are you?",
                        "answer": "I'm fine",
                        "__outputs.answer": "I'm great",
                    }
                ],
                {
                    "question": "${data.question}",
                    "answer": "${data.answer}",
                    "another_answer": "${run.outputs.answer}",
                },
                "I'm fine",
            ),
            (
                [
                    {
                        "question": "How are you?",
                        "answer": "I'm fine",
                        "__outputs.answer": "I'm great",
                    }
                ],
                {
                    "question": "${data.question}",
                    "answer": "${run.outputs.answer}",
                    "another_answer": "${data.answer}",
                },
                "I'm great",
            ),
            (
                [
                    {
                        "question": "How are you?",
                        "__outputs.answer": "I'm fine",
                        "else": "Another column",
                        "else1": "Another column 1",
                    }
                ],
                {
                    "question": "${data.question}",
                    "answer": "${run.outputs.answer}",
                    "else1": "${data.else}",
                    "else2": "${data.else1}",
                },
                "I'm fine",
            ),
        ],
    )
    def test_apply_column_mapping_target(self, json_data, inputs_mapping, answer):

        data_df = pd.DataFrame(json_data)
        new_data_df = _apply_column_mapping(data_df, inputs_mapping)

        assert "question" in new_data_df.columns
        assert "answer" in new_data_df.columns

        assert new_data_df["question"][0] == "How are you?"
        assert new_data_df["answer"][0] == answer
        if "another_answer" in inputs_mapping:
            assert "another_answer" in new_data_df.columns
            assert new_data_df["another_answer"][0] != answer
        if "else" in inputs_mapping:
            assert "else1" in new_data_df.columns
            assert new_data_df["else1"][0] == "Another column"
            assert "else2" in new_data_df.columns
            assert new_data_df["else2"][0] == "Another column 1"

    def test_evaluate_invalid_evaluator_config(self, mock_model_config, evaluate_test_data_jsonl_file):
        # Invalid source reference
        with pytest.raises(ValueError) as exc_info:
            evaluate(
                data=evaluate_test_data_jsonl_file,
                evaluators={"g": GroundednessEvaluator(model_config=mock_model_config)},
                evaluator_config={"g": {"question": "${foo.question}"}},
            )

        assert (
            "Unexpected references detected in 'evaluator_config'. Ensure only ${target.} and ${data.} are used."
            in exc_info.value.args[0]
        )

    def test_renaming_column(self):
        """Test that the columns are renamed correctly."""
        df = pd.DataFrame(
            {
                "just_column": ["just_column."],
                "presnt_generated": ["Is present in data set."],
                "__outputs.presnt_generated": ["This was generated by target."],
                "__outputs.generated": ["Generaged by target"],
                "outputs.before": ["Despite prefix this column was before target."],
            }
        )
        df_expected = pd.DataFrame(
            {
                "inputs.just_column": ["just_column."],
                "inputs.presnt_generated": ["Is present in data set."],
                "outputs.presnt_generated": ["This was generated by target."],
                "outputs.generated": ["Generaged by target"],
                "inputs.outputs.before": ["Despite prefix this column was before target."],
            }
        )
        df_actuals = _rename_columns_conditionally(df)
        assert_frame_equal(df_actuals.sort_index(axis=1), df_expected.sort_index(axis=1))

    @pytest.mark.parametrize("use_pf_client", [True, False])
    def test_evaluate_output_path(self, evaluate_test_data_jsonl_file, tmpdir, use_pf_client):
        output_path = os.path.join(tmpdir, "eval_test_results.jsonl")
        result = evaluate(
            data=evaluate_test_data_jsonl_file,
            evaluators={"g": F1ScoreEvaluator()},
            output_path=output_path,
            _use_pf_client=use_pf_client,
        )

        assert result is not None
        assert os.path.exists(output_path)
        assert os.path.isfile(output_path)

        with open(output_path, "r") as f:
            content = f.read()
            data_from_file = json.loads(content)
            assert result["metrics"] == data_from_file["metrics"]

        result = evaluate(
            data=evaluate_test_data_jsonl_file,
            evaluators={"g": F1ScoreEvaluator()},
            output_path=os.path.join(tmpdir),
        )

        with open(os.path.join(tmpdir, DEFAULT_EVALUATION_RESULTS_FILE_NAME), "r") as f:
            content = f.read()
            data_from_file = json.loads(content)
            assert result["metrics"] == data_from_file["metrics"]

    def test_evaluate_with_errors(self):
        """Test evaluate_handle_errors"""
        data = _get_file("yeti_questions.jsonl")
        result = evaluate(data=data, evaluators={"yeti": _yeti_evaluator})
        result_df = pd.DataFrame(result["rows"])
        expected = pd.read_json(data, lines=True)
        expected.rename(columns={"question": "inputs.question", "answer": "inputs.answer"}, inplace=True)

        expected["outputs.yeti.result"] = expected["inputs.answer"].str.len()
        expected.at[0, "outputs.yeti.result"] = np.nan
        expected.at[2, "outputs.yeti.result"] = np.nan
        expected.at[3, "outputs.yeti.result"] = np.nan
        assert_frame_equal(expected, result_df)

    @patch("promptflow.evals.evaluate._evaluate._evaluate")
    def test_evaluate_main_entry_guard(self, mock_evaluate, evaluate_test_data_jsonl_file):
        err_msg = (
            "An attempt has been made to start a new process before the\n        "
            "current process has finished its bootstrapping phase."
        )
        mock_evaluate.side_effect = RuntimeError(err_msg)

        with pytest.raises(RuntimeError) as exc_info:
            evaluate(
                data=evaluate_test_data_jsonl_file,
                evaluators={"f1_score": F1ScoreEvaluator()},
            )

        assert "Please ensure the evaluate API is properly guarded with the '__main__' block" in exc_info.value.args[0]

    def test_get_trace_destination(self, mock_validate_trace_destination, mock_project_scope):
        pf_client = PFClient()
        trace_destination_without_override = pf_client._config.get_trace_destination()

        pf_client = PFClient(
            config={
                "trace.destination": _trace_destination_from_project_scope(mock_project_scope)
                if mock_project_scope
                else None
            }
        )

        trace_destination_with_override = pf_client._config.get_trace_destination()

        assert trace_destination_with_override != trace_destination_without_override
        assert trace_destination_with_override == _trace_destination_from_project_scope(mock_project_scope)
