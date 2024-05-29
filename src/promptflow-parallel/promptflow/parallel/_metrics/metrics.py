# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import json
import os
from typing import Any, Dict, Mapping

from promptflow.contracts.run_info import Status
from promptflow.parallel._metrics.sender import MetricsSender
from promptflow.storage.run_records import LineRunRecord, NodeRunRecord


class Metrics(Mapping[str, Any]):
    def __init__(self, metrics: Dict[str, Any] = None, sender: MetricsSender = None):
        self._metrics = metrics or {}
        self._sender: MetricsSender = sender or MetricsSender()

    def send(self):
        self._sender.send(self._metrics)

    def __str__(self):
        return json.dumps(self._metrics)

    def __getitem__(self, __key):
        return self._metrics.__getitem__(__key)

    def __len__(self):
        return self._metrics.__len__()

    def __iter__(self):
        return self._metrics.__iter__()


class SystemMetrics(Metrics):
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
