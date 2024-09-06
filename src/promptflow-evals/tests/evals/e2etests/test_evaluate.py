import json
import os
import pathlib
import time

import numpy as np
import pandas as pd
import pytest
import requests

from promptflow.evals.evaluate import evaluate
from promptflow.evals.evaluators import (
    ContentSafetyEvaluator,
    F1ScoreEvaluator,
    FluencyEvaluator,
    GroundednessEvaluator,
)

try:
    from promptflow.recording.record_mode import is_in_ci_pipeline
except ModuleNotFoundError:
    # The file is being imported by the local test
    pass


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


def _get_run_from_run_history(flow_run_id, ml_client, project_scope):
    """Get run info from run history"""
    from azure.identity import DefaultAzureCredential

    token = "Bearer " + DefaultAzureCredential().get_token("https://management.azure.com/.default").token
    headers = {
        "Authorization": token,
        "Content-Type": "application/json",
    }
    workspace = ml_client.workspaces.get(project_scope["project_name"])
    endpoint = workspace.discovery_url.split("discovery")[0]
    pattern = (
        f"/subscriptions/{project_scope['subscription_id']}"
        f"/resourceGroups/{project_scope['resource_group_name']}"
        f"/providers/Microsoft.MachineLearningServices"
        f"/workspaces/{project_scope['project_name']}"
    )
    url = endpoint + "history/v1.0" + pattern + "/rundata"

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


@pytest.mark.usefixtures("recording_injection")
@pytest.mark.localtest
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

    def test_evaluate_with_relative_data_path(self, model_config):
        original_working_dir = os.getcwd()

        try:
            working_dir = os.path.dirname(__file__)
            os.chdir(working_dir)

            data_file = "data/evaluate_test_data.jsonl"
            input_data = pd.read_json(data_file, lines=True)

            groundedness_eval = GroundednessEvaluator(model_config)
            fluency_eval = FluencyEvaluator(model_config)

            # Run the evaluation
            result = evaluate(
                data=data_file,
                evaluators={"grounded": groundedness_eval, "fluency": fluency_eval},
            )

            row_result_df = pd.DataFrame(result["rows"])
            metrics = result["metrics"]

            # Validate the results
            assert result is not None
            assert result["rows"] is not None
            assert row_result_df.shape[0] == len(input_data)

            assert "outputs.grounded.gpt_groundedness" in row_result_df.columns.to_list()
            assert "outputs.fluency.gpt_fluency" in row_result_df.columns.to_list()

            assert "grounded.gpt_groundedness" in metrics.keys()
            assert "fluency.gpt_fluency" in metrics.keys()
        finally:
            os.chdir(original_working_dir)

    @pytest.mark.azuretest
    def test_evaluate_with_content_safety_evaluator(self, project_scope, data_file):
        input_data = pd.read_json(data_file, lines=True)

        # CS evaluator tries to store the credential, which breaks multiprocessing at
        # pickling stage. So we pass None for credential and let child evals
        # generate a default credential at runtime.
        # Internal Parallelism is also disabled to avoid faulty recordings.
        content_safety_eval = ContentSafetyEvaluator(project_scope, credential=None, parallel=False)

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

    @pytest.mark.performance_test
    def test_evaluate_with_async_enabled_evaluator(self, model_config, data_file):
        os.environ["PF_EVALS_BATCH_USE_ASYNC"] = "true"
        fluency_eval = FluencyEvaluator(model_config)

        start_time = time.time()
        result = evaluate(
            data=data_file,
            evaluators={
                "fluency": fluency_eval,
            },
        )
        end_time = time.time()
        duration = end_time - start_time

        row_result_df = pd.DataFrame(result["rows"])
        metrics = result["metrics"]

        # validate the results
        assert result is not None
        assert result["rows"] is not None
        input_data = pd.read_json(data_file, lines=True)
        assert row_result_df.shape[0] == len(input_data)
        assert "outputs.fluency.gpt_fluency" in row_result_df.columns.to_list()
        assert "fluency.gpt_fluency" in metrics.keys()
        assert duration < 10, f"evaluate API call took too long: {duration} seconds"
        os.environ.pop("PF_EVALS_BATCH_USE_ASYNC")

    @pytest.mark.parametrize(
        "use_pf_client,function,column",
        [
            (True, answer_evaluator, "length"),
            (False, answer_evaluator, "length"),
            (True, answer_evaluator_int, "output"),
            (False, answer_evaluator_int, "output"),
            (True, answer_evaluator_int_dict, "42"),
            (False, answer_evaluator_int_dict, "42"),
        ],
    )
    def test_evaluate_python_function(self, data_file, use_pf_client, function, column):
        # data
        input_data = pd.read_json(data_file, lines=True)

        # run the evaluation
        result = evaluate(data=data_file, evaluators={"answer": function}, _use_pf_client=use_pf_client)

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

    @pytest.mark.skipif(is_in_ci_pipeline(), reason="This test fails in CI and needs to be investigate. Bug: 3458432")
    @pytest.mark.azuretest
    def test_evaluate_track_in_cloud(
        self,
        questions_file,
        azure_ml_client,
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
        remote_run = _get_run_from_run_history(run_id, azure_ml_client, project_scope)

        assert remote_run is not None
        assert remote_run["runMetadata"]["properties"]["azureml.promptflow.local_to_cloud"] == "true"
        assert remote_run["runMetadata"]["properties"]["runType"] == "eval_run"
        assert remote_run["runMetadata"]["displayName"] == evaluation_name

    @pytest.mark.skipif(is_in_ci_pipeline(), reason="This test fails in CI and needs to be investigate. Bug: 3458432")
    @pytest.mark.azuretest
    def test_evaluate_track_in_cloud_no_target(
        self,
        data_file,
        azure_ml_client,
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
        remote_run = _get_run_from_run_history(run_id, azure_ml_client, project_scope)

        assert remote_run is not None
        assert remote_run["runMetadata"]["properties"]["_azureml.evaluation_run"] == "azure-ai-generative-parent"
        assert remote_run["runMetadata"]["displayName"] == evaluation_name

    @pytest.mark.parametrize(
        "return_json, aggregate_return_json",
        [
            (True, True),
            (True, False),
            (False, True),
            (False, False),
        ],
    )
    def test_evaluate_aggregation_with_threadpool(self, data_file, return_json, aggregate_return_json):
        from .custom_evaluators.answer_length_with_aggregation import AnswerLength

        result = evaluate(
            data=data_file,
            evaluators={
                "answer_length": AnswerLength(return_json=return_json, aggregate_return_json=aggregate_return_json),
                "f1_score": F1ScoreEvaluator(),
            },
        )
        assert result is not None
        assert "metrics" in result
        if aggregate_return_json:
            assert "answer_length.median" in result["metrics"].keys()

    @pytest.mark.parametrize(
        "return_json, aggregate_return_json",
        [
            (True, True),
            (True, False),
            (False, True),
            (False, False),
        ],
    )
    def test_evaluate_aggregation(self, data_file, return_json, aggregate_return_json):
        from .custom_evaluators.answer_length_with_aggregation import AnswerLength

        result = evaluate(
            data=data_file,
            evaluators={
                "answer_length": AnswerLength(return_json=return_json, aggregate_return_json=aggregate_return_json),
                "f1_score": F1ScoreEvaluator(),
            },
        )
        assert result is not None
        assert "metrics" in result
        if aggregate_return_json:
            assert "answer_length.median" in result["metrics"].keys()

    @pytest.mark.skip(reason="TODO: Add test back")
    def test_prompty_with_threadpool_implementation(self):
        pass
