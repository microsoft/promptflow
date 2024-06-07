import os
import pathlib

import pytest
import pandas as pd
from promptflow.evals.evaluate._evaluate import _aggregate_metrics
from promptflow.evals.evaluators import ContentSafetyEvaluator


def _get_file(name):
    """Get the file from the unittest data folder."""
    data_path = os.path.join(pathlib.Path(__file__).parent.resolve(), "data")
    return os.path.join(data_path, name)


@pytest.mark.unittest
class TestContentSafetyDefectRate:
    def test_content_safety_defect_rate(self):
        file_path = _get_file("validate_defect_rate_test_data.jsonl")
        df = pd.read_json(file_path, lines=True, orient="records")
        df = df.fillna('n/a')
        metrics = _aggregate_metrics(df, {"content_safety": ContentSafetyEvaluator})

        assert metrics["content_safety.hate_unfairness_defect_rate"] == 0.33
