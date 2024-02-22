# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from pathlib import Path
from typing import Any, Mapping, Optional

from promptflow.contracts.run_mode import RunMode
from promptflow.executor._service._errors import FlowFilePathInvalid
from promptflow.executor._service.contracts.base_request import BaseRequest


class BaseExecutionRequest(BaseRequest):
    """Base request model for execution."""

    run_id: str
    working_dir: Path
    flow_file: Path
    output_dir: Path
    log_path: str
    connections: Optional[Mapping[str, Any]] = None
    environment_variables: Optional[Mapping[str, Any]] = None

    def get_run_mode(self):
        raise NotImplementedError(f"Request type {self.__class__.__name__} is not implemented.")

    def validate_request(self):
        if self.flow_file.is_absolute():
            raise FlowFilePathInvalid(
                message_format=(
                    "The flow file path ({flow_file}) is invalid. The path should be relative to the working directory."
                ),
                flow_file=self.flow_file.as_posix(),
            )


class FlowExecutionRequest(BaseExecutionRequest):
    """Request model for flow execution."""

    inputs: Mapping[str, Any] = None

    def get_run_mode(self):
        return RunMode.Test


class NodeExecutionRequest(BaseExecutionRequest):
    """Request model for node execution."""

    node_name: str
    flow_inputs: Mapping[str, Any] = None
    dependency_nodes_outputs: Mapping[str, Any] = None

    def get_run_mode(self):
        return RunMode.SingleNode
