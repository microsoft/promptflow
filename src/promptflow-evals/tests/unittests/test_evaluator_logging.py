# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import pytest
import logging

from unittest.mock import patch

from promptflow.evals.evaluators.f1_score import F1ScoreEvaluator


class TestEvaluatorLogging:

    @pytest.mark.parametrize(
        "log_level,expected",
        [
            (logging.INFO, set(['flowinvoker'])),
            (logging.WARNING, set()),
        ])
    def test_f1_score_evaluator_logs(self, caplog, log_level, expected):
        """Test logging with f1 score_evaluator."""
        # Note we are not checking for 'execution.flow' as caplog
        # cannot catch it as this logger does not have a root logger as a parent.
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
        assert {'flowinvoker'}.intersection(log_called) == expected
