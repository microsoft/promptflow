# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from typing import Any, Mapping, Optional

from pydantic import BaseModel


class BaseRequest(BaseModel):
    """Base request model which contains the operation context."""

    operation_context: Optional[Mapping[str, Any]] = None
