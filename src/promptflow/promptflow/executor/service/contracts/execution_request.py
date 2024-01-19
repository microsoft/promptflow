# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from typing import Any, Mapping

from pydantic import BaseModel


class BaseExecutionRequest(BaseModel):
    run_id: str
    working_dir: str
    flow_file: str
    output_dir: str
    environment_variables: Mapping[str, Any] = None
    log_path: str


class FlowExecutionRequest(BaseExecutionRequest):
    inputs: Mapping[str, Any] = None


class NodeExecutionRequest(BaseExecutionRequest):
    node_name: str
    flow_inputs: Mapping[str, Any] = None
    dependency_nodes_outputs: Mapping[str, Any] = None
