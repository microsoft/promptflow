# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import json
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Iterable, List, Optional, Tuple, Union

from promptflow._utils.multimedia_utils import persist_multimedia_data
from promptflow._utils.utils import DataClassEncoder
from promptflow.contracts.run_info import FlowRunInfo, RunInfo
from promptflow.integrations.parallel_run._config import parser
from promptflow.integrations.parallel_run._config.model import ParallelRunConfig
from promptflow.integrations.parallel_run._executor.base import AbstractExecutor
from promptflow.integrations.parallel_run._model import Result, Row
from promptflow.integrations.parallel_run._processor.aggregation_finalizer import AggregationFinalizer
from promptflow.integrations.parallel_run._processor.debug_info import DebugInfo
from promptflow.integrations.parallel_run._processor.finalizer import CompositeFinalizer, Finalizer


class AbstractParallelRunProcessor(ABC):
    def __init__(self, working_dir: Path):
        self._working_dir = working_dir
        self._config: Optional[ParallelRunConfig] = None
        self._executor: Optional[AbstractExecutor] = None
        self._debug_info: Optional[DebugInfo] = None

    def init(self):
        self._config = parser.parse(sys.argv[1:])
        self._executor = self._create_executor(self._config)
        self._debug_info = DebugInfo(self._config.debug_output_dir)
        self._debug_info.prepare()

    @abstractmethod
    def _create_executor(self, config: ParallelRunConfig) -> AbstractExecutor:
        raise NotImplementedError

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
        return list(map(self._serialize, results))

    def _do_process(self, rows: Iterable[Row]) -> Iterable[Result]:
        for row in rows:
            yield self._executor.execute(row)

    def _serialize(self, result: Result) -> str:
        result_dict = dict(self._extract_result(result))
        return json.dumps(result_dict, cls=DataClassEncoder)

    def _extract_result(self, result: Result) -> Iterable[Tuple[str, Any]]:
        yield "output", result.output.output
        if self._executor.has_aggregation_node:
            yield "aggregation_inputs", result.output.aggregation_inputs
            yield "inputs", result.input

    def finalize(self):
        with self._resolve_finalizer() as finalizer:
            if finalizer.process_enabled:
                for row in self._read_outputs():
                    finalizer.process(row)

    def _resolve_finalizer(self) -> Finalizer:
        finalizers = [AggregationFinalizer(self._executor.has_aggregation_node, self._executor)]
        finalizers.extend(self._finalizers())
        return CompositeFinalizer(finalizers) if len(finalizers) > 1 else finalizers[0]

    def _finalizers(self) -> Iterable[Finalizer]:
        yield from []

    def _read_outputs(self) -> Iterable[Row]:
        output_files = [f for f in self._config.output_dir.glob(self._config.output_file_pattern)]
        file_count = len(output_files)
        print(f"There are {file_count} temp files to concat in finalization stage: {output_files}")
        for file_path in output_files:
            with open(file_path, "r") as f:
                for index, line in enumerate(f):
                    try:
                        row = Row.from_json(line)
                        yield row
                    except Exception:
                        print(f"Failed to process the line {index} of file {file_path}: {line}.")
                        raise

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

    def generate_flow_artifacts_file_name_by_line_number(self, line_number: int, debug_file_batch_size: int):
        """Generate flow artifacts file name."""
        section_start = line_number // debug_file_batch_size * debug_file_batch_size
        return self.generate_flow_artifacts_file_name_by_line_range(section_start, debug_file_batch_size)

    @staticmethod
    def generate_flow_artifacts_file_name_by_line_range(start_line_number: int, line_count: int):
        """Generate flow artifacts file name."""
        section_start = start_line_number
        section_end = section_start + line_count - 1
        return "{0:09d}_{1:09d}.jsonl".format(section_start, section_end)
