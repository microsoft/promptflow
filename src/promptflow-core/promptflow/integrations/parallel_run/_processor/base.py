# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable, List, Optional, Union

from promptflow._utils.multimedia_utils import persist_multimedia_data
from promptflow.contracts.run_info import FlowRunInfo, RunInfo
from promptflow.integrations.parallel_run._config import parser
from promptflow.integrations.parallel_run._config.model import ParallelRunConfig
from promptflow.integrations.parallel_run._executor.base import AbstractExecutor
from promptflow.integrations.parallel_run._model import Result, Row


class AbstractParallelRunProcessor(ABC):
    def __init__(self, working_dir: Path):
        self._working_dir = working_dir
        self._config: Optional[ParallelRunConfig] = None
        self._executor: Optional[AbstractExecutor] = None

    def init(self):
        self._config = parser.parse(sys.argv[1:])
        self._executor = self._create_executor(self._config)

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

    @abstractmethod
    def _do_process(self, rows: Iterable[Row]) -> Iterable[Result]:
        raise NotImplementedError

    def finalize(self):
        pass

    @abstractmethod
    def _create_executor(self, config: ParallelRunConfig) -> AbstractExecutor:
        raise NotImplementedError

    @staticmethod
    def _serialize_multimedia_data(run_info: Union[FlowRunInfo, RunInfo], base_dir: Path):
        """Persist multimedia data."""
        if run_info.inputs:
            run_info.inputs = persist_multimedia_data(run_info.inputs, base_dir=base_dir)
        if run_info.output:
            run_info.output = persist_multimedia_data(run_info.output, base_dir=base_dir)
            if run_info.result:
                run_info.result = run_info.output
        if run_info.api_calls:
            run_info.api_calls = persist_multimedia_data(run_info.api_calls, base_dir=base_dir)

    @staticmethod
    def generate_flow_artifacts_file_name_by_line_range(start_line_number: int, line_count: int):
        """Generate flow artifacts file name."""
        section_start = start_line_number
        section_end = section_start + line_count - 1
        return "{0:09d}_{1:09d}.jsonl".format(section_start, section_end)
