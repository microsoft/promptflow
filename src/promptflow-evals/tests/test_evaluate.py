'''
Created on Apr 2, 2024

@author: nirovins
'''
import os
import unittest

import pandas as pd

from promptflow.evals.evaluate._evaluate import evaluate
from promptflow.evals.evaluators import f1_score
import tempfile


class TestEvaluate(unittest.TestCase):

    def test_evaluate(self):
        """Test evaluate function."""
        data = pd.DataFrame(
            [["Energy is the quantitative property that is transferred to a body or to "
              "a physical system, recognizable in the performance of work"] * 2],
            columns=["groundtruth", "prediction"])

        evals = {'f1_score': os.path.join(os.path.dirname(f1_score.__file__), 'flow')}
        with tempfile.TemporaryDirectory() as d:
            out_file = os.path.join(d, 'metrics.json')
            in_file = os.path.join(d, 'data.jsonl')
            data.to_json(in_file, orient='records', lines=True, index=False)
            metrics = evaluate(
                evaluation_name='test_eval',
                target=None,  # Not used yet
                data=in_file,
                evaluators=evals,
                output_path=out_file)
            # self.assertTrue(os.path.isfile(out_file))
            self.assertIsNotNone(metrics['metrics'])


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
