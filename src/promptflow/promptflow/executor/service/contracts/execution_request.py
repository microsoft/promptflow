# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from typing import Any, Mapping

from pydantic import BaseModel

from promptflow.contracts.run_mode import RunMode


class BaseExecutionRequest(BaseModel):
    run_id: str
    working_dir: str
    flow_file: str
    output_dir: str
    connections: Mapping[str, Any] = None
    environment_variables: Mapping[str, Any] = None
    log_path: str

    def get_run_mode(self):
        raise NotImplementedError(f"Request type {self.__class__.__name__} is not implemented.")


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
