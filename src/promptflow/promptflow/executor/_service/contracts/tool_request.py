# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from pathlib import Path
from typing import Mapping

from pydantic import BaseModel


class ToolMetaRequest(BaseModel):
    working_dir: Path
    tools: Mapping[str, Mapping[str, str]]
