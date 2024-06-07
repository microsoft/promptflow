# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import random
from pathlib import Path
from unittest.mock import Mock, patch

from promptflow.executor import FlowExecutor, FlowValidator
from promptflow.executor._result import LineResult
from promptflow.parallel._config.model import ParallelRunConfig
from promptflow.parallel._executor.base import AbstractExecutor
from promptflow.parallel._model import Row


class MockExecutor(AbstractExecutor):
    @staticmethod
    def setup_test():
        return patch.object(FlowValidator, "resolve_flow_inputs_type", lambda _, row: row)

    def _create_flow_executor(self, connections: dict, config: ParallelRunConfig) -> FlowExecutor:
        return Mock(exec_line=self._mock_exec_line)

    @staticmethod
    def _mock_exec_line(inputs, index=None, **_):
        output = dict(inputs)
        if index:
            output["line_number"] = index
        return LineResult(output=output, aggregation_inputs={}, run_info=Mock(), node_run_infos={})


def test_base_executor():
    executor = MockExecutor(Path("."), Mock(input_mapping={}))
    with executor.setup_test():
        executor.init()

        row = Row.from_dict({"content": "test"}, random.randint(0, 100))
        result = executor.execute(row)

        assert result.input == row
        assert result.output.output["content"] == "test"
        assert result.output.output["line_number"] == row.row_number
