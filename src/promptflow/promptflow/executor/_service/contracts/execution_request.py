# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from pathlib import Path
from typing import Any, Mapping

from pydantic import BaseModel

from promptflow.contracts.run_mode import RunMode
from promptflow.executor._service._errors import FlowFilePathInvalid


class BaseExecutionRequest(BaseModel):
    run_id: str
    working_dir: Path
    flow_file: Path
    output_dir: Path
    connections: Mapping[str, Any] = None
    environment_variables: Mapping[str, Any] = None
    log_path: str

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
    inputs: Mapping[str, Any] = None

    def get_run_mode(self):
        return RunMode.Test


class NodeExecutionRequest(BaseExecutionRequest):
    node_name: str
    flow_inputs: Mapping[str, Any] = None
    dependency_nodes_outputs: Mapping[str, Any] = None

    def get_run_mode(self):
        return RunMode.SingleNode
