# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import itertools
import json
import shutil
import tempfile
from pathlib import Path
from typing import IO, Iterable, Tuple

from promptflow.parallel._metrics.metrics import SystemMetrics
from promptflow.storage.run_records import LineRunRecord, NodeRunRecord


class DebugInfo:
    def __init__(self, debug_output_dir: Path, debug_file_batch_size=25):
        self._debug_output_dir = debug_output_dir
        self._flow_debug_output_dir = self._debug_output_dir / "flow_artifacts"
        self._node_debug_output_dir = self._debug_output_dir / "node_artifacts"
        self._meta_file = self._debug_output_dir / "meta.json"
        self._debug_file_batch_size = debug_file_batch_size

    @staticmethod
    def temporary(prefix="prs_pf_debug_", debug_file_batch_size=25):
        return DebugInfo(Path(tempfile.mkdtemp(prefix=prefix)), debug_file_batch_size)

    def prepare(self) -> None:
        self._flow_debug_output_dir.mkdir(parents=True, exist_ok=True)
        self._node_debug_output_dir.mkdir(parents=True, exist_ok=True)
        self._meta_file.write_text(json.dumps({"batch_size": self._debug_file_batch_size}) + "\n")

    def move_to(self, other: "DebugInfo"):
        shutil.copytree(self._debug_output_dir, other._debug_output_dir, dirs_exist_ok=True)
        shutil.rmtree(self._debug_output_dir)

    def write(self, line_run_record: LineRunRecord, node_run_records: Iterable[NodeRunRecord]) -> SystemMetrics:
        file = self._flow_debug_output_dir / self.generate_flow_artifacts_file_name_by_line_number(
            line_run_record.line_number
        )

        with file.open("a") as f:
            self._write_line(f, line_run_record.serialize())
        system_metrics = self._write_nodes(node_run_records)
        return system_metrics

    def write_batch(self, run_records: Iterable[Tuple[LineRunRecord, Iterable[NodeRunRecord]]]) -> SystemMetrics:
        it = iter(run_records)
        first_line, first_line_nodes = next(it)
        file = self._flow_debug_output_dir / self.generate_flow_artifacts_file_name_by_line_range(
            first_line.line_number, self._debug_file_batch_size
        )

        system_metrics = SystemMetrics()
        with file.open("w") as f:
            for line_run_record, node_run_records in itertools.chain([(first_line, first_line_nodes)], it):
                self._write_line(f, line_run_record.serialize())
                system_metrics.merge_line_run_record(line_run_record)

                node_metrics = self._write_nodes(node_run_records)
                system_metrics.merge(node_metrics)

        return system_metrics

    def _write_nodes(self, node_run_records: Iterable[NodeRunRecord]) -> SystemMetrics:
        system_metrics = SystemMetrics()
        for node in node_run_records:
            system_metrics.merge_node_run_record(node)

            file = self._node_debug_output_dir / node.node_name / f"{node.line_number:09d}.jsonl"
            file.parent.mkdir(parents=True, exist_ok=True)

            with file.open("w") as f:
                self._write_line(f, node.serialize())
        return system_metrics

    @staticmethod
    def _write_line(io: IO, content: str):
        io.write(content)
        io.write("\n")

    @property
    def flow_output_dir(self):
        return self._flow_debug_output_dir

    def node_output_dir(self, node_name: str):
        return self._node_debug_output_dir / node_name

    def generate_flow_artifacts_file_name_by_line_number(self, line_number: int):
        """Generate flow artifacts file name."""
        section_start = line_number // self._debug_file_batch_size * self._debug_file_batch_size
        return self.generate_flow_artifacts_file_name_by_line_range(section_start, self._debug_file_batch_size)

    @staticmethod
    def generate_flow_artifacts_file_name_by_line_range(start_line_number: int, line_count: int):
        """Generate flow artifacts file name."""
        section_start = start_line_number
        section_end = section_start + line_count - 1
        return "{0:09d}_{1:09d}.jsonl".format(section_start, section_end)
