# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from pathlib import Path
from typing import Any, Mapping, Optional

from promptflow._constants import LINE_TIMEOUT_SEC
from promptflow.executor._service.contracts.base_request import BaseRequest


class InitializationRequest(BaseRequest):
    """Request model for teh batch run initialization."""

    flow_file: Path
    working_dir: Path
    output_dir: Path
    log_path: Path
    line_count: int
    worker_count: int
    connections: Optional[Mapping[str, Any]] = None
    line_timeout_sec: Optional[int] = LINE_TIMEOUT_SEC
    environment_variables: Optional[Mapping[str, Any]] = None


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
