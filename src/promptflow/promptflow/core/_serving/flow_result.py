# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from dataclasses import dataclass
from typing import Any, Mapping

from promptflow.contracts.run_info import FlowRunInfo
from promptflow.contracts.run_info import RunInfo as NodeRunInfo


@dataclass
class FlowResult:
    """The result of a flow call."""

    output: Mapping[str, Any]
    # trace info of the flow run.
    run_info: FlowRunInfo
    node_run_infos: Mapping[str, NodeRunInfo]
    # if return the response original value, only will set to true when eager flow returns non dict value.
    response_original_value: bool = False
