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
        :type status: str or :class:`Status`
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
    :type node: str
    :param flow_run_id: The id of the flow run
    :type flow_run_id: str
    :param run_id: The id of the run, which equals ``flow_run_id:step_run_id``
    :type run_id: str
    :param status: Status of the run
    :type status: ~promptflow.contracts.run_info.Status
    :param inputs: List of inputs for the run
    :type inputs: list
    :param output: Output of the run
    :type output: object
    :param metrics: Metrics of the run
    :type metrics: Dict[str, Any]
    :param error: Errors occurred during the run
    :type error: Dict[str, Any]
    :param parent_run_id: Parent run id
    :type parent_run_id: str
    :param start_time: Start time of the run
    :type start_time: datetime
    :param end_time: End time of the run
    :type end_time: datetime
    :param index: Index of the run
    :type index: Optional[int]
    :param api_calls: API calls made during the run
    :type api_calls: Optional[List[Dict[str, Any]]]
    :param variant_id: Variant id of the run
    :type variant_id: Optional[str]
    :param cached_run_id: Cached run id
    :type cached_run_id: Optional[str]
    :param cached_flow_run_id: Cached flow run id
    :type cached_flow_run_id: Optional[str]
    :param logs: Logs of the run
    :type logs: Optional[Dict[str, str]]
    :param system_metrics: System metrics of the run
    :type system_metrics: Optional[Dict[str, Any]]
    :param result: Result of the run
    :type result: Optional[object]
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

    :param run_id: The id of the run, which equals ``flow_run_id:child_flow_run_id``
    :type run_id: str
    :param status: Status of the flow run
    :type status: ~promptflow.contracts.run_info.Status
    :param error: Errors occurred during the flow run
    :type error: Dict[str, Any]
    :param inputs: Inputs for the flow run
    :type inputs: object
    :param output: Output of the flow run
    :type output: object
    :param metrics: Metrics of the flow run
    :type metrics: Dict[str, Any]
    :param request: Request made for the flow run
    :type request: object
    :param parent_run_id: Parent run id of the flow run
    :type parent_run_id: str
    :param root_run_id: Root run id of the flow run
    :type root_run_id: str
    :param source_run_id: The run id of the run that triggered the flow run
    :type source_run_id: str
    :param flow_id: Flow id of the flow run
    :type flow_id: str
    :param start_time: Start time of the flow run
    :type start_time: datetime
    :param end_time: End time of the flow run
    :type end_time: datetime
    :param index: Index of the flow run (used for bulk test mode)
    :type index: Optional[int]
    :param api_calls: API calls made during the flow run
    :type api_calls: Optional[List[Dict[str, Any]]]
    :param variant_id: Variant id of the flow run
    :type variant_id: Optional[str]
    :param name: Name of the flow run
    :type name: Optional[str]
    :param description: Description of the flow run
    :type description: Optional[str]
    :param tags: Tags of the flow run
    :type tags: Optional[Dict[str, str]]
    :param system_metrics: System metrics of the flow run
    :type system_metrics: Optional[Dict[str, Any]]
    :param result: Result of the flow run
    :type result: Optional[object]
    :param upload_metrics: Flag indicating whether to upload metrics for the flow run
    :type upload_metrics: Optional[bool]
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
