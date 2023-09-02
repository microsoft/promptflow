# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional


class Status(Enum):
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
        if isinstance(status, Status):
            status = status.value
        return status in {s.value for s in {Status.Completed, Status.Failed, Status.Bypassed, Status.Canceled}}


@dataclass
class RunInfo:
    node: str  # Node name
    flow_run_id: str  # This is equal to root_run_id
    run_id: str  # flow_run_id:step_run_id
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
    run_id: str  # flow_run_id:child_flow_run_id
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
