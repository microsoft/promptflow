import json
import os
import pathlib

import numpy as np
import pandas as pd
import pytest
import requests
from azure.identity import DefaultAzureCredential

from promptflow.evals.evaluate import evaluate
from promptflow.evals.evaluators import ContentSafetyEvaluator, F1ScoreEvaluator, GroundednessEvaluator


@pytest.fixture
def data_file():
    data_path = os.path.join(pathlib.Path(__file__).parent.resolve(), "data")
    return os.path.join(data_path, "evaluate_test_data.jsonl")


@pytest.fixture
def questions_file():
    data_path = os.path.join(pathlib.Path(__file__).parent.resolve(), "data")
    return os.path.join(data_path, "questions.jsonl")


def answer_evaluator(answer):
    return {"length": len(answer)}


def answer_evaluator_int(answer):
    return len(answer)


def answer_evaluator_int_dict(answer):
    return {42: len(answer)}


def answer_evaluator_json(answer):
    return json.dumps({"length": len(answer)})


def question_evaluator(question):
    return {"length": len(question)}


def _get_run_from_run_history(flow_run_id, runs_operation):
    """Get run info from run history"""
    token = "Bearer " + DefaultAzureCredential().get_token("https://management.azure.com/.default").token
    headers = {
        "Authorization": token,
        "Content-Type": "application/json",
    }
    url = runs_operation._run_history_endpoint_url + "/rundata"

    payload = {
        "runId": flow_run_id,
        "selectRunMetadata": True,
        "selectRunDefinition": True,
        "selectJobSpecification": True,
    }

    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        run = response.json()
        # if original_form is True, return the original run data from run history, mainly for test use
        return run
    elif response.status_code == 404:
        raise Exception(f"Run {flow_run_id!r} not found.")
    else:
        raise Exception(f"Failed to get run from service. Code: {response.status_code}, text: {response.text}")


@pytest.mark.usefixtures("recording_injection", "vcr_recording")
@pytest.mark.e2etest
class TestEvaluate:
    def test_evaluate_with_groundedness_evaluator(self, model_config, data_file):
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
        assert result["studio_url"] is None

    @pytest.mark.skip(reason="Failed in CI pipeline. Pending for investigation.")
    def test_evaluate_with_content_safety_evaluator(self, project_scope, data_file, azure_cred):
        input_data = pd.read_json(data_file, lines=True)

        content_safety_eval = ContentSafetyEvaluator(project_scope, credential=azure_cred)

        # run the evaluation
        result = evaluate(
            data=data_file,
            evaluators={"content_safety": content_safety_eval},
        )

        row_result_df = pd.DataFrame(result["rows"])
        metrics = result["metrics"]

        # validate the results
        assert result is not None
        assert result["rows"] is not None
        assert row_result_df.shape[0] == len(input_data)

        assert "outputs.content_safety.sexual" in row_result_df.columns.to_list()
        assert "outputs.content_safety.violence" in row_result_df.columns.to_list()
        assert "outputs.content_safety.self_harm" in row_result_df.columns.to_list()
        assert "outputs.content_safety.hate_unfairness" in row_result_df.columns.to_list()

        assert "content_safety.sexual_defect_rate" in metrics.keys()
        assert "content_safety.violence_defect_rate" in metrics.keys()
        assert "content_safety.self_harm_defect_rate" in metrics.keys()
        assert "content_safety.hate_unfairness_defect_rate" in metrics.keys()

        assert 0 <= metrics.get("content_safety.sexual_defect_rate") <= 1
        assert 0 <= metrics.get("content_safety.violence_defect_rate") <= 1
        assert 0 <= metrics.get("content_safety.self_harm_defect_rate") <= 1
        assert 0 <= metrics.get("content_safety.hate_unfairness_defect_rate") <= 1

    @pytest.mark.parametrize(
        "use_thread_pool,function,column",
        [
            (True, answer_evaluator, "length"),
            (False, answer_evaluator, "length"),
            (True, answer_evaluator_int, "output"),
            (False, answer_evaluator_int, "output"),
            (True, answer_evaluator_int_dict, "42"),
            (False, answer_evaluator_int_dict, "42"),
        ],
    )
    def test_evaluate_python_function(self, data_file, use_thread_pool, function, column):
        # data
        input_data = pd.read_json(data_file, lines=True)

        # run the evaluation
        result = evaluate(data=data_file, evaluators={"answer": function}, _use_thread_pool=use_thread_pool)

        row_result_df = pd.DataFrame(result["rows"])
        metrics = result["metrics"]

        # validate the results
        assert result is not None
        assert result["rows"] is not None
        assert row_result_df.shape[0] == len(input_data)

        out_column = f"outputs.answer.{column}"
        metric = f"answer.{column}"
        assert out_column in row_result_df.columns.to_list()
        assert metric in metrics.keys()
        assert metrics.get(metric) == np.nanmean(row_result_df[out_column])
        assert row_result_df[out_column][2] == 31

    def test_evaluate_with_target(self, questions_file):
        """Test evaluation with target function."""
        # We cannot define target in this file as pytest will load
        # all modules in test folder and target_fn will be imported from the first
        # module named test_evaluate and it will be a different module in unit test
        # folder. By keeping function in separate file we guarantee, it will be loaded
        # from there.
        from .target_fn import target_fn

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

    @pytest.mark.parametrize(
        "evaluation_config",
        [
            None,
            {"default": {}},
            {"default": {}, "question_ev": {}},
            {"default": {"question": "${target.question}"}},
            {"default": {"question": "${data.question}"}},
            {"default": {}, "question_ev": {"question": "${data.question}"}},
            {"default": {}, "question_ev": {"question": "${target.question}"}},
            {"default": {}, "question_ev": {"another_question": "${target.question}"}},
            {"default": {"another_question": "${target.question}"}},
        ],
    )
    def test_evaluate_another_questions(self, questions_file, evaluation_config):
        """Test evaluation with target function."""
        from .target_fn import target_fn3

        # run the evaluation with targets
        result = evaluate(
            target=target_fn3,
            data=questions_file,
            evaluators={
                "question_ev": question_evaluator,
            },
            evaluator_config=evaluation_config,
        )
        row_result_df = pd.DataFrame(result["rows"])
        assert "outputs.answer" in row_result_df.columns
        assert "inputs.question" in row_result_df.columns
        assert "outputs.question" in row_result_df.columns
        assert "outputs.question_ev.length" in row_result_df.columns
        question = "outputs.question"

        mapping = None
        if evaluation_config:
            mapping = evaluation_config.get("question_ev", evaluation_config.get("default", None))
        if mapping and ("another_question" in mapping or mapping["question"] == "${data.question}"):
            question = "inputs.question"
        expected = list(row_result_df[question].str.len())
        assert expected == list(row_result_df["outputs.question_ev.length"])

    @pytest.mark.parametrize(
        "evaluate_config",
        [
            (
                {
                    "f1_score": {
                        "answer": "${data.context}",
                        "ground_truth": "${data.ground_truth}",
                    },
                    "answer": {
                        "answer": "${target.response}",
                    },
                }
            ),
            (
                {
                    "default": {
                        "answer": "${target.response}",
                        "ground_truth": "${data.ground_truth}",
                    },
                }
            ),
        ],
    )
    def test_evaluate_with_evaluator_config(self, questions_file, evaluate_config):
        input_data = pd.read_json(questions_file, lines=True)
        from .target_fn import target_fn2

        # run the evaluation
        result = evaluate(
            data=questions_file,
            target=target_fn2,
            evaluators={"f1_score": F1ScoreEvaluator(), "answer": answer_evaluator},
            evaluator_config=evaluate_config,
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

    @pytest.mark.skip(reason="az login in fixture is not working on ubuntu and mac.Works on windows")
    def test_evaluate_track_in_cloud(
        self,
        questions_file,
        azure_pf_client,
        mock_trace_destination_to_cloud,
        project_scope,
    ):
        """Test evaluation with target function."""
        # We cannot define target in this file as pytest will load
        # all modules in test folder and target_fn will be imported from the first
        # module named test_evaluate and it will be a different module in unit test
        # folder. By keeping function in separate file we guarantee, it will be loaded
        # from there.
        from .target_fn import target_fn

        f1_score_eval = F1ScoreEvaluator()
        evaluation_name = "test_evaluate_track_in_cloud"
        # run the evaluation with targets
        result = evaluate(
            azure_ai_project=project_scope,
            evaluation_name=evaluation_name,
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
        assert result["studio_url"] is not None

        # get remote run and validate if it exists
        run_id = result["studio_url"].split("?")[0].split("/")[5]
        remote_run = azure_pf_client.runs.get(run_id)

        assert remote_run is not None
        assert remote_run.properties["azureml.promptflow.local_to_cloud"] == "true"
        assert remote_run.properties["runType"] == "eval_run"
        assert remote_run.display_name == evaluation_name

    @pytest.mark.skip(reason="az login in fixture is not working on ubuntu and mac.Works on windows")
    def test_evaluate_track_in_cloud_no_target(
        self,
        data_file,
        azure_pf_client,
        mock_trace_destination_to_cloud,
        project_scope,
    ):
        # data
        input_data = pd.read_json(data_file, lines=True)

        f1_score_eval = F1ScoreEvaluator()
        evaluation_name = "test_evaluate_track_in_cloud_no_target"

        # run the evaluation
        result = evaluate(
            azure_ai_project=project_scope,
            evaluation_name=evaluation_name,
            data=data_file,
            evaluators={"f1_score": f1_score_eval},
        )

        row_result_df = pd.DataFrame(result["rows"])
        metrics = result["metrics"]

        # validate the results
        assert result is not None
        assert result["rows"] is not None
        assert row_result_df.shape[0] == len(input_data)
        assert "outputs.f1_score.f1_score" in row_result_df.columns.to_list()
        assert "f1_score.f1_score" in metrics.keys()
        assert metrics.get("f1_score.f1_score") == np.nanmean(row_result_df["outputs.f1_score.f1_score"])
        assert row_result_df["outputs.f1_score.f1_score"][2] == 1
        assert result["studio_url"] is not None

        # get remote run and validate if it exists
        run_id = result["studio_url"].split("?")[0].split("/")[5]
        remote_run = _get_run_from_run_history(run_id, azure_pf_client.runs)

        assert remote_run is not None
        assert remote_run["runMetadata"]["properties"]["_azureml.evaluation_run"] == "azure-ai-generative-parent"
        assert remote_run["runMetadata"]["displayName"] == evaluation_name

    @pytest.mark.skip(reason="TODO: Add test back")
    def test_prompty_with_threadpool_implementation(self):
        pass
