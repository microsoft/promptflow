from typing import Any, List, Optional, Type

import inspect
import os
import pytest

from promptflow.evals import evaluators
from promptflow.evals.evaluators import content_safety


@pytest.mark.unittest
class TestSaveEval:
    """Test saving evaluators."""

    @staticmethod
    def _get_evaluators_from_module(namespace: Any, exceptions: Optional[List[str]] = None) -> List[Type]:
        evaluators = []
        for name, obj in inspect.getmembers(namespace):
            if inspect.isclass(obj):
                if exceptions and name in exceptions:
                    continue
                evaluators.append(obj)
        return evaluators

    EVALUATORS = _get_evaluators_from_module(evaluators)
    RAI_EVALUATORS = _get_evaluators_from_module(content_safety)

    @pytest.mark.parametrize('evaluator', EVALUATORS)
    def test_save_evaluators(self, tmpdir, pf_client, evaluator) -> None:
        """Test regular evaluator saving."""
        pf_client.flows.save(evaluator, path=tmpdir)
        assert os.path.isfile(os.path.join(tmpdir, 'flow.flex.yaml'))

    @pytest.mark.parametrize('rai_evaluator', RAI_EVALUATORS)
    def test_save_rai_evaluators(self, tmpdir, pf_client, rai_evaluator):
        """Test saving of RAI evaluators"""
        pf_client.flows.save(rai_evaluator, path=tmpdir)
        assert os.path.isfile(os.path.join(tmpdir, 'flow.flex.yaml'))
