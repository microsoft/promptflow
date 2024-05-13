# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from typing import Any, List, Mapping, Optional, Union

from promptflow._constants import LINE_TIMEOUT_SEC
from promptflow.contracts.run_mode import RunMode
from promptflow.executor._service.contracts.base_request import BaseRequest
from promptflow.executor._service.contracts.execution_request import BaseExecutionRequest


class InitializationRequest(BaseExecutionRequest):
    """Request model for teh batch run initialization."""

    worker_count: Optional[int] = None
    line_timeout_sec: Optional[int] = LINE_TIMEOUT_SEC
    init_kwargs: Optional[Mapping[str, Any]] = None

    def get_run_mode(self):
        return RunMode.Batch


class LineExecutionRequest(BaseRequest):
    """Request model for line execution in the batch run."""

    run_id: str
    line_number: int
    inputs: Mapping[str, Any]


class AggregationRequest(BaseRequest):
    """Request model for executing aggregation nodes in the batch run."""

    run_id: str
    batch_inputs: Optional[Mapping[str, Any]] = None
    aggregation_inputs: Union[Mapping[str, Any], List[Any]]  # The type differs between the dag flow and the flex flow.
