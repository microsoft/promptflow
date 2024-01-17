# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from typing import Any, Mapping

from pydantic import BaseModel


class BaseExecutionRequest(BaseModel):
    run_id: str
    working_dir: str
    flow_file: str
    environment_variables: Mapping[str, Any] = None
    log_path: str


class FlowExecutionRequest(BaseExecutionRequest):
    inputs: Mapping[str, Any]
    output_dir: str


class NodeExecutionRequest(BaseExecutionRequest):
    node_name: str
    inputs: Mapping[str, Any]
    output_dir: str
