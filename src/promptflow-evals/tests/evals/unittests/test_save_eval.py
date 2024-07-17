import inspect
import os
import pathlib
from typing import Any, List, Optional, Type

import pytest

from promptflow.core._errors import GenerateFlowMetaJsonError
from promptflow.evals import evaluators


@pytest.fixture
def data_file():
    data_path = os.path.join(pathlib.Path(__file__).parent.resolve(), "data")
    return os.path.join(data_path, "evaluate_test_data.jsonl")


def get_evaluators_from_module(namespace: Any, exceptions: Optional[List[str]] = None) -> List[Type]:
    evaluators = []
    for name, obj in inspect.getmembers(namespace):
        if inspect.isclass(obj):
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

    def test_relative_import_save_load(self, tmpdir, pf_client, data_file) -> None:
        """Test loading and running an evaluator with a relative import, and ensure
        that the expected error message occurs.

        Debugging context. An loaded and executed evaluator acts like a main module in that it's __package__
        value is not set, which causes relative imports to fail. Attempts to set __package__ can potentially work,
        but that requires that the loaded directory be added to sys.modules as a functional module, which is non-trivial
        enough that I gave up on it.

        More context on __package__: https://peps.python.org/pep-0366/
        """
        from data.toyFlexFlow.toy_flex_eval import ToyEvaluator

        pf_client.flows.save(ToyEvaluator, path=tmpdir)
        with pytest.raises(GenerateFlowMetaJsonError) as info:
            _ = pf_client.run(tmpdir, data=data_file)
        assert "Relative imports fail in evaluators that are saved and loaded." in info._excinfo[1].message
