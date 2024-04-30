# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from dataclasses import dataclass
from datetime import datetime
from itertools import chain
from typing import Any, List, Mapping

from promptflow._constants import TokenKeys
from promptflow._utils.exception_utils import ExceptionPresenter, RootErrorCode
from promptflow.contracts.run_info import RunInfo, Status
from promptflow.executor._result import AggregationResult, LineResult
from promptflow.tracing._openai_utils import OpenAIMetricsCalculator


@dataclass
class LineError:
    """The error of a line in a batch run.

    It contains the line number and the error dict of a failed line in the batch run.
    The error dict is gengerated by ExceptionPresenter.to_dict().
    """

    line_number: int
    error: Mapping[str, Any]

    def to_dict(self):
        return {
            "line_number": self.line_number,
            "error": self.error,
        }


@dataclass
class ErrorSummary:
    """The summary of errors in a batch run.

    :param failed_user_error_lines: The number of lines that failed with user error.
    :type failed_user_error_lines: int
    :param failed_system_error_lines: The number of lines that failed with system error.
    :type failed_system_error_lines: int
    :param error_list: The line number and error dict of failed lines in the line results.
    :type error_list: List[~promptflow.batch._result.LineError]
    :param aggr_error_dict: The dict of node name and error dict of failed nodes in the aggregation result.
    :type aggr_error_dict: Mapping[str, Any]
    :param batch_error_dict: The dict of batch run error.
    :type batch_error_dict: Mapping[str, Any]
    """

    failed_user_error_lines: int
    failed_system_error_lines: int
    error_list: List[LineError]
    aggr_error_dict: Mapping[str, Any]
    batch_error_dict: Mapping[str, Any]

    @staticmethod
    def create(line_results: List[LineResult], aggr_result: AggregationResult, exception: Exception = None):
        failed_user_error_lines = 0
        failed_system_error_lines = 0
        error_list: List[LineError] = []

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
            aggr_error_dict={
                node_name: node_run_info.error
                for node_name, node_run_info in aggr_result.node_run_infos.items()
                if node_run_info.status == Status.Failed
            },
            batch_error_dict=ExceptionPresenter.create(exception).to_dict() if exception else None,
        )
        return error_summary


@dataclass
class SystemMetrics:
    """The system metrics of a batch run."""

    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    duration: float  # in seconds

    @staticmethod
    def create(
        start_time: datetime, end_time: datetime, line_results: List[LineResult], aggr_results: AggregationResult
    ):
        openai_metrics = SystemMetrics._get_openai_metrics(line_results, aggr_results)
        return SystemMetrics(
            total_tokens=openai_metrics.get("total_tokens", 0),
            prompt_tokens=openai_metrics.get("prompt_tokens", 0),
            completion_tokens=openai_metrics.get("completion_tokens", 0),
            duration=(end_time - start_time).total_seconds(),
        )

    @staticmethod
    def _get_openai_metrics(line_results: List[LineResult], aggr_results: AggregationResult):
        # Get openai metrics from the flow run info in line results, since the flex flow do not have node run infos.
        flow_run_infos = (line_result.run_info for line_result in line_results)
        aggr_node_run_infos = (node_run_info for node_run_info in aggr_results.node_run_infos.values())
        total_metrics = {}
        calculator = OpenAIMetricsCalculator()
        for run_info in chain(flow_run_infos, aggr_node_run_infos):
            metrics = SystemMetrics._try_get_openai_metrics(run_info)
            if metrics:
                calculator.merge_metrics_dict(total_metrics, metrics)
            else:
                api_calls = run_info.api_calls or []
                for call in api_calls:
                    metrics = calculator.get_openai_metrics_from_api_call(call)
                    calculator.merge_metrics_dict(total_metrics, metrics)
        return total_metrics

    def _try_get_openai_metrics(run_info: RunInfo):
        openai_metrics = {}
        if run_info.system_metrics:
            for metric in TokenKeys.get_all_values():
                if metric in run_info.system_metrics:
                    openai_metrics[metric] = run_info.system_metrics[metric]
        return openai_metrics

    def to_dict(self):
        return {
            "total_tokens": self.total_tokens,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "duration": self.duration,
        }


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
    system_metrics: SystemMetrics
    error_summary: ErrorSummary

    @classmethod
    def create(
        cls,
        start_time: datetime,
        end_time: datetime,
        line_results: List[LineResult],
        aggr_result: AggregationResult,
        status: Status = Status.Completed,
        exception: Exception = None,
    ) -> "BatchResult":
        total_lines = len(line_results)
        completed_lines = sum(line_result.run_info.status == Status.Completed for line_result in line_results)
        failed_lines = total_lines - completed_lines

        if exception:
            status = Status.Failed

        return cls(
            status=status,
            total_lines=total_lines,
            completed_lines=completed_lines,
            failed_lines=failed_lines,
            node_status=BatchResult._get_node_status(line_results, aggr_result),
            start_time=start_time,
            end_time=end_time,
            metrics=aggr_result.metrics,
            system_metrics=SystemMetrics.create(start_time, end_time, line_results, aggr_result),
            error_summary=ErrorSummary.create(line_results, aggr_result, exception),
        )

    @staticmethod
    def _get_node_status(line_results: List[LineResult], aggr_result: AggregationResult):
        node_run_infos = _get_node_run_infos(line_results, aggr_result)
        node_status = {}
        for node_run_info in node_run_infos:
            key = f"{node_run_info.node}.{node_run_info.status.value.lower()}"
            node_status[key] = node_status.get(key, 0) + 1
        return node_status


def _get_node_run_infos(line_results: List[LineResult], aggr_result: AggregationResult):
    line_node_run_infos = (
        node_run_info for line_result in line_results for node_run_info in line_result.node_run_infos.values()
    )
    aggr_node_run_infos = (node_run_info for node_run_info in aggr_result.node_run_infos.values())
    return chain(line_node_run_infos, aggr_node_run_infos)
