# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from pathlib import Path
from typing import Any, Mapping

from pydantic import BaseModel


class ToolMetaRequest(BaseModel):
    """Request model for generating tool meta."""

    working_dir: Path
    tools: Mapping[str, Mapping[str, str]]


class RetrieveToolFuncResultRequest(BaseModel):
    """Request model for retrieving tool function result."""

    func_path: str
    func_kwargs: Mapping[str, Any]
    func_call_scenario: str = None
    ws_triple: Mapping[str, str] = None
