# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from pathlib import Path
from typing import Any, Mapping, Optional

from promptflow.executor._service.contracts.base_request import BaseRequest


class ToolMetaRequest(BaseRequest):
    """Request model for generating tool meta."""

    working_dir: Path
    tools: Mapping[str, Mapping[str, str]]


class RetrieveToolFuncResultRequest(BaseRequest):
    """Request model for retrieving tool function result."""

    func_path: str
    func_kwargs: Mapping[str, Any]
    func_call_scenario: str = None
    ws_triple: Mapping[str, str] = None
    environment_variables: Optional[Mapping[str, Any]] = None
