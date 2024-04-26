# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import os
from pathlib import Path
from typing import Any, Mapping, Optional

from promptflow.contracts.run_mode import RunMode
from promptflow.executor._service._errors import FlowFilePathInvalid
from promptflow.executor._service.contracts.base_request import BaseRequest


class BaseExecutionRequest(BaseRequest):
    # Use Optional for new fields to avoid breaking existing clients
    """Base request model for execution."""

    working_dir: Path
    flow_file: Path
    output_dir: Path
    log_path: Optional[str] = None
    connections: Optional[Mapping[str, Any]] = None
    environment_variables: Optional[Mapping[str, Any]] = None
    flow_name: Optional[str] = None
    flow_logs_folder: Optional[str] = None

    def get_run_mode(self):
        raise NotImplementedError(f"Request type {self.__class__.__name__} is not implemented.")

    def validate_request(self):
        if not self.working_dir.is_absolute() or self.flow_file.is_absolute():
            raise FlowFilePathInvalid(
                message_format=(
                    "The working directory path ({working_dir}) or flow file path ({flow_file}) is invalid. "
                    "The working directory should be a absolute path and the flow file path should be "
                    "relative to the working directory."
                ),
                working_dir=self.working_dir.as_posix(),
                flow_file=self.flow_file.as_posix(),
            )
        # Ensure that the flow file path is within the working directory
        working_dir = os.path.normpath(self.working_dir)
        flow_file = os.path.normpath(self.flow_file)
        full_path = os.path.normpath(os.path.join(working_dir, flow_file))
        if not full_path.startswith(working_dir):
            raise FlowFilePathInvalid(
                message_format=(
                    "The flow file path ({flow_file}) is invalid. The path should be in the working directory."
                ),
                flow_file=self.flow_file.as_posix(),
            )
        self.working_dir = Path(working_dir)
        self.flow_file = Path(flow_file)


class FlowExecutionRequest(BaseExecutionRequest):
    """Request model for flow execution."""

    run_id: str
    inputs: Optional[Mapping[str, Any]] = None

    def get_run_mode(self):
        return RunMode.Test


class NodeExecutionRequest(BaseExecutionRequest):
    """Request model for node execution."""

    run_id: str
    node_name: str
    flow_inputs: Mapping[str, Any] = None
    dependency_nodes_outputs: Mapping[str, Any] = None

    def get_run_mode(self):
        return RunMode.SingleNode


class CancelExecutionRequest(BaseRequest):
    """Request model for canceling execution."""

    run_id: str
