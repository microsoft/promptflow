'''
Created on Apr 12, 2024

@author: nirovins
'''
import pytest
import logging

from unittest.mock import patch

from promptflow.evals.evaluators.f1_score import F1ScoreEvaluator


class TestF1ScoreEvaluator:

    @pytest.mark.parametrize(
        "log_level,expected",
        [
            (logging.INFO, set(['flowinvoker', 'execution.flow'])),
            (logging.WARNING, set()),
        ])
    def test_f1_scre_evaluator_logs(self, caplog, log_level, expected):
        """Test logging with f1 score_evaluator."""
        def mock_get(name: str, verbosity: int = logging.INFO, target_stdout: bool = False):
            logger = logging.getLogger(name)
            logger.setLevel(verbosity)
            return logger

        with patch('promptflow._utils.logger_utils.LoggerFactory') as mock_factory:
            mock_factory.get_logger = mock_get
            F1ScoreEvaluator(log_level=log_level)(
                answer='June is the coldest summer month.',
                ground_truth='January is the coldest winter month.'
            )
        log_called = {lg.name for lg in caplog.records}
        assert {'flowinvoker', 'execution.flow'}.intersection(log_called) == expected
