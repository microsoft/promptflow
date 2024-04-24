# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import json
import os
from typing import Any, Dict, List, Mapping

from promptflow.contracts.run_info import FlowRunInfo, RunInfo, Status
from promptflow.integrations.parallel_run._metrics.sender import MetricsSender
from promptflow.storage.run_records import LineRunRecord, NodeRunRecord


class Metrics:
    def __init__(self, metrics: Dict[str, Any] = None, sender: MetricsSender = None):
        self._metrics = metrics or {}
        self._sender: MetricsSender = sender or MetricsSender()

    def send(self):
        self._sender.send(self._metrics)

    def __str__(self):
        return json.dumps(self._metrics)


class SystemMetrics(Metrics):
    def __init__(self, metrics: Dict[str, Any] = None, sender: MetricsSender = None):
        super().__init__(metrics, sender)

    def merge_line_run_record(self, line_run_record: LineRunRecord):
        completed = 1 if Status(line_run_record.status) == Status.Completed else 0
        self._metrics["__pf__.lines.total"] = self._metrics.get("__pf__.lines.total", 0) + 1
        self._metrics["__pf__.lines.completed"] = self._metrics.get("__pf__.lines.completed", 0) + completed
        self._metrics["__pf__.lines.failed"] = (
            self._metrics["__pf__.lines.total"] - self._metrics["__pf__.lines.completed"]
        )

    def merge_node_run_record(self, node_run_record: NodeRunRecord):
        status = Status(node_run_record.status)
        if node_run_record.line_number is not None:
            if status in (Status.Completed, Status.Bypassed, Status.Failed):
                key = f"__pf__.nodes.{node_run_record.node_name}.{node_run_record.status.lower()}"
                self._metrics[key] = self._metrics.get(key, 0) + 1
        else:
            self._metrics[f"__pf__.nodes.{node_run_record.node_name}.completed"] = (
                1 if status == Status.Completed else 0
            )

    @classmethod
    def from_node_run_infos(cls, node_run_infos: Mapping[str, RunInfo]) -> "SystemMetrics":
        """Summarize node metrics for single line.
        See promptflow._core.run_tracker.RunTracker.get_status_summary().
        """
        status_summary = {}
        for node_name, node_run_info in node_run_infos.items():
            status = node_run_info.status
            if node_run_info is not None and node_run_info.index is not None:
                # Only consider Completed, Bypassed and Failed status, because the UX only support three status.
                if status in (Status.Completed, Status.Bypassed, Status.Failed):
                    node_status_key = f"__pf__.nodes.{node_name}.{status.value.lower()}"
                    status_summary[node_status_key] = status_summary.setdefault(node_status_key, 0) + 1
            # For reduce node, the index is None.
            else:
                status_summary[f"__pf__.nodes.{node_name}.completed"] = 1 if status == Status.Completed else 0
        return cls(status_summary)

    @classmethod
    def from_line_run_infos(cls, line_run_infos: List[FlowRunInfo]) -> "SystemMetrics":
        """Summarize line metrics.
        See promptflow._core.run_tracker.RunTracker.get_status_summary().
        """
        total_lines = len(line_run_infos)
        completed_lines = len([run_info for run_info in line_run_infos if run_info.status == Status.Completed])
        status_summary = {
            "__pf__.lines.completed": completed_lines,
            "__pf__.lines.failed": total_lines - completed_lines,
        }
        return cls(status_summary)

    @classmethod
    def from_files(cls, root: str, sender: MetricsSender = None) -> "SystemMetrics":
        """Summarize status of all line run and node run."""

        def _read(folder: str):
            """Read system metrics from files."""
            for metric_file in os.listdir(folder):
                file_path = os.path.join(folder, metric_file)
                with open(file_path, "r") as f:
                    for line in f:  # one file should have only one line
                        yield json.loads(line)

        status_summary = {}
        # accumulate status of all minibatches to get the final status summary
        for saved_metric in _read(root):
            for k, v in saved_metric.items():
                status_summary[k] = status_summary.setdefault(k, 0) + v
        return cls(status_summary, sender)

    def merge(self, other: "SystemMetrics"):
        """Merge system metrics."""
        for k, v in other._metrics.items():
            self._metrics[k] = self._metrics.setdefault(k, 0) + v
