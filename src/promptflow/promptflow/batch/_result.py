# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from dataclasses import dataclass
from datetime import datetime
from itertools import chain
from typing import Any, Dict, Iterable, List, Mapping

from promptflow._utils.exception_utils import RootErrorCode
from promptflow._utils.openai_metrics_calculator import OpenAIMetricsCalculator
from promptflow.contracts.run_info import RunInfo, Status
from promptflow.executor._result import AggregationResult, LineResult


@dataclass
class LineError:
    line_number: int
    error: Dict[str, Any]


@dataclass
class ErrorSummary:
    """The summary of errors in a batch run."""

    failed_user_error_lines: int
    failed_system_error_lines: int
    error_list: List[LineError]


@dataclass
class SystemMetrics:
    """The system metrics of a batch run."""

    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    duration: float  # in seconds


@dataclass
class BatchResult:
    """The result of a batch run."""

    status: Status
    total_lines: int
    completed_lines: int
    failed_lines: int
    node_status: Mapping[str, int]
    start_time: datetime
    end_time: datetime
    metrics: Mapping[str, str]
    system_metrics: Mapping[str, Any]
    error_summary: ErrorSummary

    @classmethod
    def summary(
        cls, start_time: datetime, line_results: List[LineResult], aggr_result: AggregationResult
    ) -> "BatchResult":
        # calculate the line status of the batch run
        total_lines = len(line_results)
        completed_lines = sum(line_result.run_info.status == Status.Completed for line_result in line_results)
        failed_lines = total_lines - completed_lines

        batch_result = cls(
            status=Status.Completed,
            total_lines=total_lines,
            completed_lines=completed_lines,
            failed_lines=failed_lines,
            start_time=start_time,
            end_time=datetime.utcnow(),
            metrics=aggr_result.metrics,
        )

        node_run_infos = batch_result._get_node_run_infos(line_results, aggr_result)
        batch_result.node_status = batch_result._get_node_status(node_run_infos)
        batch_result.system_metrics = batch_result._get_system_metrics(node_run_infos)
        batch_result.error_summary = batch_result._get_error_summary(line_results)

        return batch_result

    def _get_node_status(self, node_run_infos: Iterable[RunInfo]):
        node_status = {}
        for node_run_info in node_run_infos:
            key = f"{node_run_info.node}.{node_run_info.status.value.lower()}"
            node_status[key] = node_status.get(key, 0) + 1
        return node_status

    def _get_system_metrics(self, node_run_infos: Iterable[RunInfo]):
        openai_metrics = self._get_openai_metrics(node_run_infos)
        return SystemMetrics(
            total_tokens=openai_metrics.get("total_tokens", 0),
            prompt_tokens=openai_metrics.get("prompt_tokens", 0),
            completion_tokens=openai_metrics.get("completion_tokens", 0),
            duration=(self.end_time - self.start_time).total_seconds(),
        )

    def _get_error_summary(self, line_results: List[LineResult]):
        failed_user_error_lines = 0
        failed_system_error_lines = 0
        error_list = []

        for line_result in line_results:
            if line_result.run_info.status != Status.Failed:
                continue

            flow_run = line_result.run_info
            if flow_run.error.get("code", "") == RootErrorCode.USER_ERROR:
                failed_user_error_lines += 1
            else:
                failed_system_error_lines += 1

            line_error = LineError(
                line_number=flow_run.index,
                error=flow_run.error,
            )
            error_list.append(line_error)

        error_summary = ErrorSummary(
            failed_user_error_lines=failed_user_error_lines,
            failed_system_error_lines=failed_system_error_lines,
            error_list=sorted(error_list, key=lambda x: x.line_number),
        )
        return error_summary

    def _get_node_run_infos(self, line_results: List[LineResult], aggr_results: AggregationResult):
        line_node_run_infos = (
            node_run_info for line_result in line_results for node_run_info in line_result.node_run_infos.values()
        )
        aggr_node_run_infos = (node_run_info for node_run_info in aggr_results.node_run_infos.values())
        return chain(line_node_run_infos, aggr_node_run_infos)

    def _get_openai_metrics(self, node_run_infos: Iterable[RunInfo]):
        total_metrics = {}
        calculator = OpenAIMetricsCalculator()
        for run_info in node_run_infos:
            for call in run_info.api_calls:
                metrics = calculator.get_openai_metrics_from_api_call(call)
                calculator.merge_metrics_dict(total_metrics, metrics)
        return total_metrics
