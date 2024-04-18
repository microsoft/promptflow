# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Iterable, Mapping

from promptflow.contracts.run_info import FlowRunInfo, RunInfo
from promptflow.integrations.parallel_run._config.model import ParallelRunConfig
from promptflow.integrations.parallel_run._executor.bulk_executor import BulkRunExecutor
from promptflow.integrations.parallel_run._metrics.metrics import SystemMetrics
from promptflow.integrations.parallel_run._model import Result, Row
from promptflow.integrations.parallel_run._processor.base import AbstractParallelRunProcessor
from promptflow.storage.run_records import LineRunRecord, NodeRunRecord


class BulkRunProcessor(AbstractParallelRunProcessor):
    def _do_process(self, rows: Iterable[Row]) -> Iterable[Result]:
        first_row_number = None
        debug_infos = []
        for row in rows:
            if not first_row_number:
                first_row_number = row.row_number

            line_result = self._executor.execute(row)
            debug_infos.append((line_result.run_info, line_result.node_run_infos))

            yield Result(line_result.output, line_result.aggregation_inputs, row)

        if not self._executor.is_debug_enabled or not debug_infos:
            return

        row_count = len(debug_infos)
        system_metrics = SystemMetrics.from_line_run_infos([run_info for run_info, _ in debug_infos])

        with self._open_flow_debug_file(first_row_number, row_count) as (file, f):
            for run_info, node_run_infos in debug_infos:
                self._write_flow_debug_info(file, f, run_info)
                self._write_node_debug_info(node_run_infos)
                system_metrics.merge(SystemMetrics.from_node_run_infos(node_run_infos))
        self._write_system_metrics(system_metrics, first_row_number, row_count)

    @contextmanager
    def _open_flow_debug_file(self, first_row_number: int, row_count: int):
        folder = self._config.debug_output_dir / "flow_artifacts"
        folder.mkdir(parents=True, exist_ok=True)

        filename = self.generate_flow_artifacts_file_name_by_line_range(first_row_number, row_count)
        file = folder / filename

        with open(file, "w") as f:
            yield file, f

    def _write_flow_debug_info(self, file: Path, file_io: IO, run_info: FlowRunInfo):
        self._serialize_multimedia_data(run_info, file.parent)
        file_io.write(LineRunRecord.from_run_info(run_info).serialize())
        file_io.write("\n")

    def _write_node_debug_info(self, node_run_infos: Mapping[str, RunInfo]):
        folder = self._config.debug_output_dir / "node_artifacts"
        for node_name, node_run_info in node_run_infos.items():
            file = folder / node_name / "{0:09d}.jsonl".format(node_run_info.index)
            file.parent.mkdir(parents=True, exist_ok=True)

            self._serialize_multimedia_data(node_run_info, file.parent)
            with open(file, "w") as f:
                f.write(NodeRunRecord.from_run_info(node_run_info).serialize())
                f.write("\n")

    def _write_system_metrics(self, system_metrics: SystemMetrics, first_row_number: int, row_count: int):
        folder = self._config.debug_output_dir / "system_metrics"
        folder.mkdir(parents=True, exist_ok=True)

        filename = self.generate_flow_artifacts_file_name_by_line_range(first_row_number, row_count)
        file = folder / filename
        with open(file, "w") as f:
            f.write(str(system_metrics))

    def _create_executor(self, config: ParallelRunConfig):
        return BulkRunExecutor(self._working_dir, config)
