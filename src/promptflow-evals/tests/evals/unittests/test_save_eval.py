import inspect
import os
import pathlib
from enum import Enum
from typing import Any, List, Optional, Type

import pytest

from promptflow.evals import evaluators


@pytest.fixture
def data_file():
    data_path = os.path.join(pathlib.Path(__file__).parent.resolve(), "data")
    return os.path.join(data_path, "evaluate_test_data.jsonl")


def get_evaluators_from_module(namespace: Any, exceptions: Optional[List[str]] = None) -> List[Type]:
    evaluators = []
    for name, obj in inspect.getmembers(namespace):
        if inspect.isclass(obj) and not issubclass(obj, Enum):
            if exceptions and name in exceptions:
                continue
            evaluators.append(obj)
    return evaluators


@pytest.mark.unittest
class TestSaveEval:
    """Test saving evaluators."""

    EVALUATORS = get_evaluators_from_module(evaluators)

    @pytest.mark.parametrize("evaluator", EVALUATORS)
    def test_save_evaluators(self, tmpdir, pf_client, evaluator) -> None:
        """Test regular evaluator saving."""
        pf_client.flows.save(evaluator, path=tmpdir)
        assert os.path.isfile(os.path.join(tmpdir, "flow.flex.yaml"))

    def test_load_and_run_evaluators(self, tmpdir, pf_client, data_file) -> None:
        """Test regular evaluator saving."""
        from promptflow.evals.evaluators import F1ScoreEvaluator

        pf_client.flows.save(F1ScoreEvaluator, path=tmpdir)
        run = pf_client.run(tmpdir, data=data_file)
        results_df = pf_client.get_details(run.name)

        assert results_df is not None
        assert results_df["outputs.f1_score"].notnull().all()
