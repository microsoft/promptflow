# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from dataclasses import dataclass
from typing import Mapping, Any
from promptflow.contracts.run_info import FlowRunInfo
from promptflow.contracts.run_info import RunInfo as NodeRunInfo


@dataclass
class FlowResult:
    """The result of a flow call."""

    output: Mapping[str, Any]
    # trace info of the flow run.
    run_info: FlowRunInfo
    node_run_infos: Mapping[str, NodeRunInfo]
