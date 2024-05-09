# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from pathlib import Path
from typing import Iterable, Tuple
from unittest.mock import Mock

from promptflow.executor._result import LineResult
from promptflow.parallel._config.model import ParallelRunConfig
from promptflow.parallel._executor.base import ParallelRunExecutor
from promptflow.parallel._model import Result, Row
from promptflow.parallel._processor.base import AbstractParallelRunProcessor
from promptflow.parallel._processor.finalizer import Finalizer


class MockProcessor(AbstractParallelRunProcessor):
    def __init__(self):
        super().__init__(working_dir=Path("."), args=["--output", "."])
        self._executed_results = []
        self.finalizer = MockFinalizer()

    def _create_executor(self, config: ParallelRunConfig) -> ParallelRunExecutor:
        return Mock(execute=self._execute, has_aggregation_node=False)

    @staticmethod
    def _execute(row: Row) -> Result:
        return Result(
            input=row, output=LineResult(output=dict(row), aggregation_inputs={}, run_info=None, node_run_infos={})
        )

    def _serialize(self, result: Result) -> str:
        res = super()._serialize(result)
        self._executed_results.append(res)
        return res

    def _read_output_lines(self) -> Iterable[Tuple[str, str]]:
        for result in self._executed_results:
            yield "/mock/file/path", result

    def _finalizers(self) -> Iterable[Finalizer]:
        yield self.finalizer


class MockFinalizer(Finalizer):
    def __init__(self):
        self.processed = 0

    @property
    def process_enabled(self) -> bool:
        return True

    def process(self, row: Row) -> None:
        self.processed += 1


def test_processor():
    processor = MockProcessor()
    processor.init()

    rows = [{"a": i} for i in range(10)]
    results = processor.process(rows, Mock(minibatch_index=0, global_row_index_lower_bound=0))
    assert len(results) == len(rows)

    processor.finalize()
    assert processor.finalizer.processed == len(rows)
