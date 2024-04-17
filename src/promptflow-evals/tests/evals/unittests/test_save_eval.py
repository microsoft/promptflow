from typing import Any, List, Optional

import inspect
import os
import tempfile
import unittest
from promptflow.client import PFClient
from promptflow.evals import evaluators
from promptflow.evals.evaluators import content_safety


class TestSaveEval(unittest.TestCase):
    """Test saving evaluators."""

    def setUp(self) -> None:
        self.pf = PFClient()
        unittest.TestCase.setUp(self)

    def _do_test_saving(self,
                        namespace: Any,
                        exceptions: Optional[List[str]] = None) -> None:
        """Do the actual test on saving evaluators."""
        for name, obj in inspect.getmembers(namespace):
            if inspect.isclass(obj):
                if exceptions and name in exceptions:
                    continue
                with tempfile.TemporaryDirectory() as d:
                    self.pf.flows.save(obj, path=d)
                    self.assertTrue(os.path.isfile(os.path.join(d, 'flow.flex.yaml')))

    def test_save_evaluators(self) -> None:
        """Test regular evaluator saving."""
        self._do_test_saving(evaluators, ['ChatEvaluator'])

    @unittest.skip('RAI models constructor contains credentials, which is not supported.')
    def test_save_rai_evaluators(self):
        """Test saving of RAI evaluators"""
        self._do_test_saving(content_safety)


if __name__ == "__main__":
    unittest.main()
