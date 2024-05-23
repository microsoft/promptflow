# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Iterable, List, Optional, Tuple, Union

from promptflow._utils.multimedia_utils import persist_multimedia_data
from promptflow.contracts.run_info import FlowRunInfo, RunInfo
from promptflow.parallel._config import parser
from promptflow.parallel._config.model import ParallelRunConfig
from promptflow.parallel._executor.base import ParallelRunExecutor
from promptflow.parallel._model import Result, Row
from promptflow.parallel._processor.aggregation_finalizer import AggregationFinalizer
from promptflow.parallel._processor.debug_info import DebugInfo
from promptflow.parallel._processor.finalizer import CompositeFinalizer, Finalizer
from promptflow.parallel.processor import ParallelRunProcessor
from promptflow.parallel.utils import DataClassEncoder


class AbstractParallelRunProcessor(ParallelRunProcessor, ABC):
    def __init__(self, working_dir: Path, args: List[str]):
        self._working_dir = working_dir
        self._args = args
        self._config: Optional[ParallelRunConfig] = None
        self._executor: Optional[ParallelRunExecutor] = None
        self._debug_info: Optional[DebugInfo] = None
        self._logger = logging.getLogger(self.__class__.__name__)

    def init(self):
        self._config = parser.parse(self._args)
        self._executor = self._create_executor(self._config)
        self._executor.init()
        self._debug_info = (
            DebugInfo(self._config.debug_output_dir) if self._config.is_debug_enabled else DebugInfo.temporary()
        )
        self._debug_info.prepare()

    @abstractmethod
    def _create_executor(self, config: ParallelRunConfig) -> ParallelRunExecutor:
        raise NotImplementedError

    def process(self, mini_batch: List[dict], context) -> List[str]:
        minibatch_id = context.minibatch_index
        self._logger.info(f"PromptFlow executor received data index {minibatch_id}")

        global_row_index_lower_bound = context.global_row_index_lower_bound
        self._logger.info(f"PromptFlow executor received global_row_index_lower_bound {global_row_index_lower_bound}")

        row_count = len(mini_batch)
        self._logger.info(f"PromptFlow executor received row count {row_count}")

        rows = (
            Row.from_dict(data, row_number=global_row_index_lower_bound + idx) for idx, data in enumerate(mini_batch)
        )
        results = self._do_process(rows)
        return list(map(self._serialize, results))

    def _do_process(self, rows: Iterable[Row]) -> Iterable[Result]:
        for row in rows:
            yield self._executor.execute(row)

    def _serialize(self, result: Result) -> str:
        result_dict = dict(self._collect_result_for_serialization(result))
        return json.dumps(result_dict, cls=DataClassEncoder)

    def _collect_result_for_serialization(self, result: Result) -> Iterable[Tuple[str, Any]]:
        yield "output", result.output.output
        if self._executor.has_aggregation_node:
            yield "aggregation_inputs", result.output.aggregation_inputs
            yield "inputs", dict(result.input)  # Mapping is not serializable
        yield from self._extract_result(result)

    def _extract_result(self, result: Result) -> Iterable[Tuple[str, Any]]:
        # Override this method to extract additional information from the result
        return []

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
        # Override this method to provide additional finalizers
        return []

    def _read_outputs(self) -> Iterable[Row]:
        for index, f_line in enumerate(self._read_output_lines()):
            file_path, line = f_line
            try:
                data = json.loads(line)
                row_number = data["output"].get("line_number", index)
                yield Row.from_json(line, row_number=row_number)
            except Exception:
                self._logger.error(f"Failed to process the line {index} of file {file_path}: {line}.")
                raise

    def _read_output_lines(self) -> Iterable[Tuple[str, str]]:
        output_files = [f for f in self._config.output_dir.glob(self._config.output_file_pattern)]
        file_count = len(output_files)
        self._logger.info(f"There are {file_count} temp files to concat in finalization stage: {output_files}")

        for file_path in output_files:
            with open(file_path, "r") as f:
                for line in f:
                    yield f.name, line

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
