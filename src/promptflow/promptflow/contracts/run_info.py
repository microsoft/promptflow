# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional


class Status(Enum):
    """An enumeration class for different types of run status."""

    Running = "Running"
    Preparing = "Preparing"
    Completed = "Completed"
    Failed = "Failed"
    Bypassed = "Bypassed"
    Canceled = "Canceled"
    NotStarted = "NotStarted"
    CancelRequested = "CancelRequested"

    @staticmethod
    def is_terminated(status):
        """Check if a given status is terminated.

        :param status: The status to be checked
        :return: True if the status is terminated, False otherwise
        :rtype: bool
        """
        if isinstance(status, Status):
            status = status.value
        return status in {s.value for s in {Status.Completed, Status.Failed, Status.Bypassed, Status.Canceled}}


@dataclass
class RunInfo:
    """A dataclass representing the run information.

    :param node: Node name
    :param flow_run_id: This is equal to root_run_id
    :param run_id: flow_run_id:step_run_id
    :param status: Status of the run, see :class:`Status`
    :param inputs: List of inputs for the run
    :param output: Output of the run
    :param metrics: Metrics of the run
    :param error: Errors occurred during the run
    :param parent_run_id: Parent run id
    :param start_time: Start time of the run
    :param end_time: End time of the run
    :param index: (Optional) Index of the run
    :param api_calls: (Optional) API calls made during the run
    :param variant_id: (Optional) Variant id of the run
    :param cached_run_id: (Optional) Cached run id
    :param cached_flow_run_id: (Optional) Cached flow run id
    :param logs: (Optional) Logs of the run
    :param system_metrics: (Optional) System metrics of the run
    :param result: (Optional) Result of the run
    """

    node: str
    flow_run_id: str
    run_id: str
    status: Status
    inputs: list
    output: object
    metrics: Dict[str, Any]
    error: Dict[str, Any]
    parent_run_id: str
    start_time: datetime
    end_time: datetime
    index: Optional[int] = None
    api_calls: Optional[List[Dict[str, Any]]] = None
    variant_id: str = ""
    cached_run_id: str = None
    cached_flow_run_id: str = None
    logs: Optional[Dict[str, str]] = None
    system_metrics: Dict[str, Any] = None
    result: object = None


@dataclass
class FlowRunInfo:
    """A dataclass representing the run information.

    :param run_id: flow_run_id:child_flow_run_id
    :param status: Status of the flow run, see :class:`Status`
    :param error: Errors occurred during the flow run
    :param inputs: Inputs for the flow run
    :param output: Output of the flow run
    :param metrics: Metrics of the flow run
    :param request: Request made for the flow run
    :param parent_run_id: Parent run id of the flow run
    :param root_run_id: Root run id of the flow run
    :param source_run_id: The run id of the run that triggered the flow run
    :param flow_id: Flow id of the flow run
    :param start_time: Start time of the flow run
    :param end_time: End time of the flow run
    :param index: (Optional) Index of the flow run (used for bulk test mode)
    :param api_calls: (Optional) API calls made during the flow run
    :param variant_id: (Optional) Variant id of the flow run
    :param name: (Optional) Name of the flow run
    :param description: (Optional) Description of the flow run
    :param tags: (Optional) Tags of the flow run
    :param system_metrics: (Optional) System metrics of the flow run
    :param result: (Optional) Result of the flow run
    :param upload_metrics: (Optional) Flag indicating whether to upload metrics for the flow run
    """
    run_id: str
    status: Status
    error: object
    inputs: object
    output: object
    metrics: Dict[str, Any]
    request: object
    parent_run_id: str
    root_run_id: str
    source_run_id: str
    flow_id: str
    start_time: datetime
    end_time: datetime
    index: Optional[int] = None
    api_calls: Optional[List[Dict[str, Any]]] = None
    variant_id: str = ""
    name: str = ""
    description: str = ""
    tags: Optional[Mapping[str, str]] = None
    system_metrics: Dict[str, Any] = None
    result: object = None
    upload_metrics: bool = False  # only set as true for root runs in bulk test mode and evaluation mode
