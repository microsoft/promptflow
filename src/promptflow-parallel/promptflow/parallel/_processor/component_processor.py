# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from typing import Any, Iterable, Tuple

from promptflow.parallel._config.model import ParallelRunConfig
from promptflow.parallel._executor.base import AbstractExecutor
from promptflow.parallel._executor.component_executor import ComponentRunExecutor
from promptflow.parallel._model import Result, Row
from promptflow.parallel._processor.base import AbstractParallelRunProcessor
from promptflow.parallel._processor.debug_info import DebugInfo
from promptflow.parallel._processor.finalizer import Finalizer
from promptflow.storage.run_records import LineRunRecord, NodeRunRecord


class ComponentRunProcessor(AbstractParallelRunProcessor):
    def _create_executor(self, config: ParallelRunConfig) -> AbstractExecutor:
        return ComponentRunExecutor(self._working_dir, config)

    def _finalizers(self) -> Iterable[Finalizer]:
        yield _ComponentRunFinalizer(self._config.is_debug_enabled, self._debug_info)

    def _extract_result(self, result: Result) -> Iterable[Tuple[str, Any]]:
        if not self._config.is_debug_enabled:
            return
        yield "run_info", LineRunRecord.from_run_info(result.output.run_info)
        yield "node_run_infos", [NodeRunRecord.from_run_info(n) for n in result.output.node_run_infos.values()]


class _ComponentRunFinalizer(Finalizer):
    def __init__(self, debug_enabled: bool, debug_info: DebugInfo):
        self._debug_enabled = debug_enabled
        self._debug_info = debug_info
        self._local_temp_debug_dir = DebugInfo.temporary()
        if self._debug_enabled:
            self._local_temp_debug_dir.prepare()

    @property
    def process_enabled(self) -> bool:
        return self._debug_enabled

    def process(self, row: Row) -> None:
        line_run_record = LineRunRecord(**row["run_info"])
        node_run_records = [NodeRunRecord(**n) for n in row["node_run_infos"]]
        self._local_temp_debug_dir.write(line_run_record, node_run_records)

    def cleanup(self) -> None:
        if not self._debug_enabled:
            return
        self._local_temp_debug_dir.move_to(self._debug_info)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
