# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable, List, Optional

from promptflow.executor._result import LineResult
from promptflow.integrations.parallel_run._config import parser
from promptflow.integrations.parallel_run._config.model import ParallelRunConfig
from promptflow.integrations.parallel_run._executor.base import AbstractExecutor
from promptflow.integrations.parallel_run._model import Result, Row


class AbstractParallelRunProcessor(ABC):
    def __init__(self, working_dir: Path):
        self._working_dir = working_dir
        self._executor: Optional[AbstractExecutor] = None

    def init(self):
        config = parser.parse(sys.argv[1:])
        self._executor = self._create_executor(config)

    def process(self, mini_batch: List[dict], context) -> List[str]:
        minibatch_id = context.minibatch_index
        print(f"PromptFlow executor received data index {minibatch_id}")
        global_row_index_lower_bound = context.global_row_index_lower_bound
        print(f"PromptFlow executor received global_row_index_lower_bound {global_row_index_lower_bound}")
        row_count = len(mini_batch)
        print(f"PromptFlow executor received row count {row_count}")

        rows = (
            Row.from_dict(data, row_number=global_row_index_lower_bound + idx) for idx, data in enumerate(mini_batch)
        )
        results = self._do_process(rows)
        return [result.serialize() for result in results]

    def _do_process(self, rows: Iterable[Row]) -> Iterable[Result]:
        line_results = (self._executor.execute(row) for row in rows)
        return self._build_results(line_results)

    @abstractmethod
    def _build_results(self, line_results: Iterable[LineResult]) -> Iterable[Result]:
        raise NotImplementedError

    def finalize(self):
        pass

    @abstractmethod
    def _create_executor(self, config: ParallelRunConfig):
        raise NotImplementedError
