# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import logging
import shutil
import uuid
from pathlib import Path
from typing import Iterable, List, Tuple

from promptflow.contracts.run_info import FlowRunInfo, RunInfo
from promptflow.parallel._config.model import ParallelRunConfig
from promptflow.parallel._executor.bulk_executor import BulkRunExecutor
from promptflow.parallel._metrics.metrics import SystemMetrics
from promptflow.parallel._model import Result, Row
from promptflow.parallel._processor.base import AbstractParallelRunProcessor
from promptflow.parallel._processor.finalizer import Finalizer
from promptflow.storage.run_records import LineRunRecord, NodeRunRecord


class BulkRunProcessor(AbstractParallelRunProcessor):
    def _create_executor(self, config: ParallelRunConfig):
        return BulkRunExecutor(self._working_dir, config)

    def _finalizers(self) -> Iterable[Finalizer]:
        yield _BulkRunFinalizer(self._config.is_debug_enabled, self._system_metrics_dir)

    def _do_process(self, rows: Iterable[Row]) -> Iterable[Result]:
        debug_infos = []
        for result in super()._do_process(rows):
            debug_infos.append((result.output.run_info, result.output.node_run_infos.values()))
            yield result

        if not self._config.is_debug_enabled or not debug_infos:
            return

        debug_records = self._debug_records(debug_infos)
        system_metrics = self._debug_info.write_batch(debug_records)
        self._write_system_metrics(system_metrics)

    def _debug_records(self, debug_infos: List[Tuple[FlowRunInfo, Iterable[RunInfo]]]):
        for flow_run_info, node_run_infos in debug_infos:
            self._serialize_multimedia_data(flow_run_info, self._debug_info.flow_output_dir)
            yield LineRunRecord.from_run_info(flow_run_info), self._node_debug_records(node_run_infos)

    def _node_debug_records(self, node_run_infos: Iterable[RunInfo]):
        for node_run_info in node_run_infos:
            self._serialize_multimedia_data(node_run_info, self._debug_info.node_output_dir(node_run_info.node))
            yield NodeRunRecord.from_run_info(node_run_info)

    def _write_system_metrics(self, system_metrics: SystemMetrics):
        folder = self._system_metrics_dir
        folder.mkdir(parents=True, exist_ok=True)

        filename = str(uuid.uuid4()) + ".jsonl"
        file = folder / filename
        with open(file, "w") as f:
            f.write(str(system_metrics))

    @property
    def _system_metrics_dir(self):
        return self._config.debug_output_dir / "system_metrics"


class _BulkRunFinalizer(Finalizer):
    def __init__(self, debug_enabled: bool, system_metrics_dir: Path):
        self._debug_enabled = debug_enabled
        self._system_metrics_dir = system_metrics_dir
        self._logger = logging.getLogger(self.__class__.__name__)

    @property
    def process_enabled(self) -> bool:
        return False

    def process(self, row: Row) -> None:
        raise NotImplementedError

    def merge_system_metrics(self):
        if not self._debug_enabled:
            return
        self._logger.info("Summarizing system metrics.")
        system_metrics = SystemMetrics.from_files(str(self._system_metrics_dir))
        system_metrics.send()
        shutil.rmtree(self._system_metrics_dir, ignore_errors=True)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.merge_system_metrics()
