import os
import pathlib

import numpy as np
import pandas as pd
import pytest

from promptflow.evals.evaluate import evaluate
from promptflow.evals.evaluators import F1ScoreEvaluator, GroundednessEvaluator


def test(question, blah):
    return {"question": question, "blah": blah}


@pytest.mark.usefixtures("model_config", "recording_injection")
@pytest.mark.e2etest
class TestQualityEvaluators:
    def test_groundedness_evaluator(self, model_config, deployment_name):
        # data
        data_path = os.path.join(pathlib.Path(__file__).parent.resolve(), "data")
        data_file = os.path.join(data_path, "evaluate_test_data.jsonl")
        input_data = pd.read_json(data_file, lines=True)

        groundedness_eval = GroundednessEvaluator(model_config, deployment_name)
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
