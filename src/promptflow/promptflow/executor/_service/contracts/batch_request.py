# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from typing import Any, Mapping, Optional

from promptflow._constants import LINE_TIMEOUT_SEC
from promptflow.executor._service.contracts.base_request import BaseRequest
from promptflow.executor._service.contracts.execution_request import BaseExecutionRequest


class InitializationRequest(BaseExecutionRequest):
    """Request model for teh batch run initialization."""

    line_count: int
    worker_count: int
    line_timeout_sec: Optional[int] = LINE_TIMEOUT_SEC


class LineExecutionRequest(BaseRequest):
    """Request model for line execution in the batch run."""

    run_id: str
    line_number: int
    inputs: Mapping[str, Any]


class AggregationRequest(BaseRequest):
    """Request model for executing aggregation nodes in the batch run."""

    run_id: str
    batch_inputs: Mapping[str, Any]
    aggregation_inputs: Mapping[str, Any]
