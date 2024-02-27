# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from typing import Any, Mapping

from promptflow.executor._service.contracts.base_request import BaseRequest


class InitializationRequest(BaseRequest):
    """Request model for teh batch run initialization."""


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
